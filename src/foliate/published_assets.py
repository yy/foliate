"""Optional remote publication for generated Quarto assets.

Local assets remain Foliate's default.  When ``.foliate/assets.toml`` exists,
generated Quarto figures live in the ignored cache and deployment publishes the
figures referenced by the built site before syncing the HTML.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit

from .config import Config


class AssetPublicationError(RuntimeError):
    """Raised when generated assets cannot be prepared or published safely."""


@dataclass(frozen=True)
class PublisherConfig:
    """Command-backed publisher for one staged generated-asset tree."""

    command: tuple[str, ...]
    public_base_url: str
    key_prefix: str = "quarto"


@dataclass(frozen=True)
class PublishedBuild:
    """A deploy-ready build and its generated-asset publication summary."""

    path: Path
    asset_count: int
    dry_run: bool


def _publisher_config_path(config: Config) -> Path:
    return config.get_foliate_dir() / "assets.toml"


def load_publisher_config(
    config: Config, *, required: bool = True
) -> PublisherConfig | None:
    """Load the optional generated-asset publisher configuration."""
    path = _publisher_config_path(config)
    if not path.is_file():
        if required:
            raise AssetPublicationError(
                f"Asset publisher is not configured: create {path}"
            )
        return None

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise AssetPublicationError(f"Cannot read {path}: {error}") from error

    table = data.get("publisher")
    if not isinstance(table, dict):
        raise AssetPublicationError(f"{path} must contain a [publisher] table")

    command = table.get("command")
    if not isinstance(command, list) or not command or not all(
        isinstance(part, str) and part for part in command
    ):
        raise AssetPublicationError(
            f"[publisher].command in {path} must be a non-empty array of strings"
        )
    if not any(
        placeholder in part
        for part in command
        for placeholder in ("{staging_dir}", "{staging_prefix_dir}")
    ):
        raise AssetPublicationError(
            f"[publisher].command in {path} must include "
            "{staging_dir} or {staging_prefix_dir}"
        )

    public_base_url = table.get("public_base_url")
    if not isinstance(public_base_url, str) or not public_base_url.strip():
        raise AssetPublicationError(
            f"[publisher].public_base_url in {path} must be a non-empty string"
        )
    parsed_url = urlsplit(public_base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise AssetPublicationError(
            f"[publisher].public_base_url in {path} must be an HTTP(S) URL"
        )

    key_prefix = table.get("key_prefix", "quarto")
    if not isinstance(key_prefix, str) or not key_prefix.strip("/").strip():
        raise AssetPublicationError(
            f"[publisher].key_prefix in {path} must be a non-empty string"
        )
    normalized_prefix = key_prefix.strip("/")
    prefix_parts = normalized_prefix.split("/")
    if (
        "\\" in normalized_prefix
        or any(not part or part in {".", ".."} for part in prefix_parts)
    ):
        raise AssetPublicationError(
            f"[publisher].key_prefix in {path} must be a safe URL path"
        )

    return PublisherConfig(
        command=tuple(command),
        public_base_url=public_base_url.rstrip("/"),
        key_prefix=normalized_prefix,
    )


def publisher_is_configured(config: Config) -> bool:
    """Return whether this vault opted into remote generated assets."""
    return _publisher_config_path(config).is_file()


def get_generated_asset_root(config: Config) -> Path:
    """Return the source directory used for generated Quarto figures.

    Local-only Foliate sites keep their established ``assets/quarto`` behavior.
    A configured publisher moves generated figures into Foliate's ignored cache.
    """
    vault = config.vault_path
    if vault is None:
        raise AssetPublicationError("Foliate has no vault path")
    if publisher_is_configured(config):
        # Load here so an invalid publisher fails before Quarto writes output.
        load_publisher_config(config)
        return config.get_cache_dir() / "quarto" / "assets"
    return vault.resolve() / "assets" / "quarto"


def generated_asset_key(
    relative_path: Path, publisher: PublisherConfig
) -> str:
    """Return the stable object key overwritten by later figure versions."""
    relative = PurePosixPath(relative_path.as_posix())
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise AssetPublicationError(f"Unsafe generated asset path: {relative_path}")
    return f"{publisher.key_prefix}/{relative.as_posix()}"


def public_asset_url(key: str, publisher: PublisherConfig) -> str:
    """Join a configured public base URL to a safely encoded object key."""
    return f"{publisher.public_base_url}/{quote(key, safe='/-._~')}"


_DEPLOY_TEXT_SUFFIXES = frozenset({".html", ".json", ".xml", ".txt", ".css"})


def _load_deploy_text(build_dir: Path, asset_root: Path) -> dict[Path, str]:
    text: dict[Path, str] = {}
    for path in build_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _DEPLOY_TEXT_SUFFIXES:
            continue
        try:
            path.relative_to(asset_root)
        except ValueError:
            pass
        else:
            continue
        try:
            text[path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
    return text


def _rewrite_asset_references(
    text: dict[Path, str], local_url: str, public_url: str, site_url: str
) -> bool:
    encoded_url = quote(local_url, safe="/-._~")
    candidates = {local_url, encoded_url}
    if site_url:
        site_base = site_url.rstrip("/")
        candidates.update({f"{site_base}{local_url}", f"{site_base}{encoded_url}"})

    changed = False
    for path, content in text.items():
        rewritten = content
        # Replace fully qualified variants before their root-relative suffixes.
        for candidate in sorted(candidates, key=len, reverse=True):
            rewritten = rewritten.replace(candidate, public_url)
        if rewritten != content:
            text[path] = rewritten
            changed = True
    return changed


def _format_publish_command(
    publisher: PublisherConfig, staging_dir: Path
) -> list[str]:
    prefix_dir = staging_dir.joinpath(*PurePosixPath(publisher.key_prefix).parts)
    values = {
        "staging_dir": str(staging_dir.resolve()),
        "staging_prefix_dir": str(prefix_dir.resolve()),
        "key_prefix": publisher.key_prefix,
    }
    try:
        return [part.format_map(values) for part in publisher.command]
    except KeyError as error:
        raise AssetPublicationError(
            f"Unknown placeholder in publisher command: {error.args[0]}"
        ) from error


def prepare_published_build(
    config: Config,
    build_dir: Path,
    *,
    dry_run: bool = False,
) -> PublishedBuild:
    """Create a deploy-only build with generated-asset links resolved remotely.

    An unconfigured site returns its ordinary build unchanged.  Configured sites
    get a separate cached deployment tree so local previews retain local images.
    """
    publisher = load_publisher_config(config, required=False)
    if publisher is None:
        return PublishedBuild(build_dir, 0, dry_run)

    from .assets import robust_rmtree

    cache_dir = config.get_cache_dir() / "publisher"
    deploy_dir = cache_dir / "build"
    staging_dir = cache_dir / "staging"
    for path in (deploy_dir, staging_dir):
        if path.exists():
            robust_rmtree(path)
    shutil.copytree(build_dir, deploy_dir)
    staging_dir.mkdir(parents=True)
    staging_dir.joinpath(*PurePosixPath(publisher.key_prefix).parts).mkdir(
        parents=True
    )

    asset_root = deploy_dir / "assets" / "quarto"
    deploy_text = _load_deploy_text(deploy_dir, asset_root)
    asset_count = 0
    if asset_root.is_dir():
        for source in sorted(path for path in asset_root.rglob("*") if path.is_file()):
            relative = source.relative_to(asset_root)
            local_url = f"/assets/quarto/{relative.as_posix()}"
            key = generated_asset_key(relative, publisher)
            public_url = public_asset_url(key, publisher)
            if not _rewrite_asset_references(
                deploy_text,
                local_url,
                public_url,
                config.site.url,
            ):
                continue

            destination = staging_dir.joinpath(*PurePosixPath(key).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            asset_count += 1

        robust_rmtree(asset_root)

    for path, content in deploy_text.items():
        path.write_text(content, encoding="utf-8")

    if not dry_run:
        command = _format_publish_command(publisher, staging_dir)
        try:
            subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise AssetPublicationError(
                f"Generated-asset upload failed: {error}"
            ) from error

    return PublishedBuild(deploy_dir, asset_count, dry_run)
