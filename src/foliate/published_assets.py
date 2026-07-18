"""Publication-gated uploads for generated page assets.

The build path is deliberately read-only with respect to remote storage.  A
page opts in with ``publish_assets: true``; ``foliate publish-assets`` is the
only operation that invokes the configured uploader.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import quote

from .config import Config
from .markdown_utils import parse_markdown_file, slugify_path

R = TypeVar("R")


def _with_quarto_lock(
    function: Callable[..., R],
) -> Callable[..., R]:
    """Hold the project Quarto lock around a publication operation."""

    @wraps(function)
    def locked(config: Config, *args: object, **kwargs: object) -> R:
        from .quarto import quarto_render_lock

        with quarto_render_lock(config):
            return function(config, *args, **kwargs)

    return locked


class AssetPublicationError(RuntimeError):
    """Raised when generated assets cannot be published safely."""


@dataclass(frozen=True)
class PublisherConfig:
    """Command-backed object-store publisher configuration."""

    command: tuple[str, ...]
    url_template: str
    key_template: str = "{filename}"
    draft_root: str = "assets/drafts/quarto"
    manifest: str = ".foliate/published-assets.json"


@dataclass(frozen=True)
class PublishResult:
    """Summary of one page-asset publication run."""

    discovered: int
    uploaded: int
    unchanged: int
    dry_run: bool


def _require_string(table: dict[str, object], key: str, path: Path) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssetPublicationError(
            f"[publisher].{key} in {path} must be a non-empty string"
        )
    return value


def load_publisher_config(config: Config) -> PublisherConfig:
    """Load the optional command publisher from ``.foliate/assets.toml``."""
    path = config.get_foliate_dir() / "assets.toml"
    if not path.is_file():
        raise AssetPublicationError(
            f"Asset publisher is not configured: create {path}"
        )

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

    optional: dict[str, str] = {}
    for key, default in {
        "key_template": "{filename}",
        "draft_root": "assets/drafts/quarto",
        "manifest": ".foliate/published-assets.json",
    }.items():
        value = table.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise AssetPublicationError(
                f"[publisher].{key} in {path} must be a non-empty string"
            )
        optional[key] = value

    return PublisherConfig(
        command=tuple(command),
        url_template=_require_string(table, "url_template", path),
        **optional,
    )


def is_managed_page(qmd_file: Path) -> bool:
    """Return whether a QMD page opted into generated-asset publication."""
    metadata, _ = parse_markdown_file(qmd_file)
    return metadata.get("publish_assets") is True


def is_published_page(qmd_file: Path) -> bool:
    """Return whether a QMD page is explicitly published."""
    metadata, _ = parse_markdown_file(qmd_file)
    return metadata.get("published") is True


def set_page_published(qmd_file: Path) -> str | None:
    """Set ``published: true`` while preserving the rest of the QMD source.

    Returns the original content when a change was made so callers can restore
    it if publication fails.  An already published page returns ``None``.
    """
    try:
        original = qmd_file.read_text(encoding="utf-8")
    except OSError as error:
        raise AssetPublicationError(f"Cannot read {qmd_file}: {error}") from error
    if is_published_page(qmd_file):
        return None
    updated, count = re.subn(
        r"(?m)^(published:\s*)false\s*$",
        r"\g<1>true",
        original,
        count=1,
    )
    if count != 1:
        raise AssetPublicationError(
            f"{qmd_file.name} must contain an explicit 'published: false' field"
        )
    qmd_file.write_text(updated, encoding="utf-8")
    return original


def get_managed_asset_dir(
    config: Config, qmd_file: Path, publisher: PublisherConfig | None = None
) -> Path | None:
    """Return the per-page draft directory used by managed QMD output."""
    vault = config.vault_path
    if vault is None or not is_managed_page(qmd_file):
        return None
    try:
        relative = qmd_file.resolve().relative_to(vault.resolve())
    except ValueError:
        return None

    publisher = publisher or load_publisher_config(config)
    root = vault.resolve() / publisher.draft_root
    return root / relative.parent / relative.stem


def get_managed_asset_root(
    config: Config, publisher: PublisherConfig | None = None
) -> Path:
    """Return the root passed to Quarto for managed generated assets."""
    vault = config.vault_path
    if vault is None:
        raise AssetPublicationError("Foliate has no vault path")
    publisher = publisher or load_publisher_config(config)
    return vault.resolve() / publisher.draft_root


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(config: Config, publisher: PublisherConfig) -> Path:
    vault = config.vault_path
    if vault is None:
        raise AssetPublicationError("Foliate has no vault path")
    path = Path(publisher.manifest)
    return path if path.is_absolute() else vault.resolve() / path


def _load_manifest(config: Config, publisher: PublisherConfig) -> dict[str, Any]:
    path = _manifest_path(config, publisher)
    if not path.exists():
        return {"version": 1, "assets": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssetPublicationError(f"Cannot read {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
        raise AssetPublicationError(f"Invalid asset manifest: {path}")
    return data


def _write_manifest(
    config: Config, publisher: PublisherConfig, manifest: dict[str, Any]
) -> None:
    path = _manifest_path(config, publisher)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _relative_asset_path(config: Config, path: Path) -> str:
    vault = config.vault_path
    if vault is None:
        raise AssetPublicationError("Foliate has no vault path")
    try:
        return path.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError as error:
        raise AssetPublicationError(f"Asset is outside the vault: {path}") from error


def _format_values(
    config: Config, qmd_file: Path, source: Path, publisher: PublisherConfig
) -> dict[str, str]:
    digest = _sha256(source)
    source_rel = _relative_asset_path(config, source)
    vault = config.vault_path
    assert vault is not None
    page = qmd_file.resolve().relative_to(vault.resolve()).with_suffix("").as_posix()
    values = {
        "source": str(source.resolve()),
        "source_rel": source_rel,
        "filename": source.name,
        "stem": source.stem,
        "suffix": source.suffix,
        "page": page,
        "page_slug": slugify_path(page),
        "hash": digest,
        "hash8": digest[:8],
    }
    try:
        values["key"] = publisher.key_template.format_map(values)
    except KeyError as error:
        raise AssetPublicationError(
            f"Unknown placeholder in key_template: {error.args[0]}"
        ) from error
    return values


def _format_template(template: str, values: dict[str, str], label: str) -> str:
    try:
        return template.format_map(values)
    except KeyError as error:
        raise AssetPublicationError(
            f"Unknown placeholder in {label}: {error.args[0]}"
        ) from error


def apply_published_asset_urls(
    config: Config,
    qmd_file: Path,
    text: str,
    *,
    require_current: bool = True,
) -> str:
    """Replace managed local asset links with verified public URLs.

    Unpublished and unmanaged pages are returned unchanged.  A published page
    cannot silently point at a newly rendered but not-yet-uploaded file.
    """
    if not is_managed_page(qmd_file) or not is_published_page(qmd_file):
        return text

    publisher = load_publisher_config(config)
    manifest = _load_manifest(config, publisher)
    assets = manifest["assets"]
    managed_dir = get_managed_asset_dir(config, qmd_file, publisher)
    if managed_dir is None:
        return text

    for path in sorted(managed_dir.rglob("*")) if managed_dir.exists() else []:
        if not path.is_file():
            continue
        relative = _relative_asset_path(config, path)
        raw_url = f"/{relative}"
        encoded_url = f"/{quote(relative, safe='/')}"
        if raw_url not in text and encoded_url not in text:
            continue
        entry = assets.get(relative)
        if not isinstance(entry, dict):
            if require_current:
                raise AssetPublicationError(
                    f"{qmd_file.name} has unpublished generated asset {relative}; "
                    f"run 'foliate publish-assets {qmd_file}'"
                )
            continue
        if require_current and entry.get("sha256") != _sha256(path):
            raise AssetPublicationError(
                f"{qmd_file.name} generated asset changed: {relative}; "
                f"run 'foliate publish-assets {qmd_file}'"
            )
        public_url = entry.get("url")
        if not isinstance(public_url, str) or not public_url:
            raise AssetPublicationError(f"Manifest URL is missing for {relative}")
        text = text.replace(raw_url, public_url).replace(encoded_url, public_url)
    return text


@_with_quarto_lock
def publish_page_assets(
    config: Config,
    qmd_file: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> PublishResult:
    """Render and publish all generated assets for one managed QMD page."""
    qmd_file = qmd_file.resolve()
    if not qmd_file.is_file():
        raise AssetPublicationError(f"Page does not exist: {qmd_file}")
    if qmd_file.suffix.lower() != ".qmd":
        raise AssetPublicationError("publish-assets currently accepts QMD pages only")
    if not is_managed_page(qmd_file):
        raise AssetPublicationError(
            f"{qmd_file.name} must set 'publish_assets: true' in frontmatter"
        )
    if not is_published_page(qmd_file):
        raise AssetPublicationError(
            f"Refusing to upload {qmd_file.name}: set 'published: true' first"
        )

    publisher = load_publisher_config(config)

    # Import lazily to avoid a module cycle: quarto uses the URL rewriter above.
    from .quarto import (
        get_cached_markdown_path,
        get_preview_markdown_path,
        preprocess_quarto,
    )

    rendered = preprocess_quarto(
        config,
        force=True,
        single_file=qmd_file,
        validate_published_assets=False,
    )
    if str(qmd_file) not in rendered:
        raise AssetPublicationError(f"Quarto did not render {qmd_file}")

    asset_dir = get_managed_asset_dir(config, qmd_file, publisher)
    if asset_dir is None or not asset_dir.is_dir():
        raise AssetPublicationError(
            f"No generated asset directory found for {qmd_file}"
        )
    files = sorted(path for path in asset_dir.rglob("*") if path.is_file())
    if not files:
        raise AssetPublicationError(f"No generated assets found for {qmd_file}")

    manifest = _load_manifest(config, publisher)
    assets = manifest["assets"]
    candidates: list[tuple[Path, str, dict[str, str]]] = []
    seen_keys: set[str] = set()
    unchanged = 0
    for source in files:
        relative = _relative_asset_path(config, source)
        values = _format_values(config, qmd_file, source, publisher)
        if values["key"] in seen_keys:
            raise AssetPublicationError(
                f"Multiple generated assets resolve to key {values['key']!r}"
            )
        seen_keys.add(values["key"])
        current = assets.get(relative)
        if (
            not force
            and isinstance(current, dict)
            and current.get("sha256") == values["hash"]
        ):
            unchanged += 1
        else:
            candidates.append((source, relative, values))

    if dry_run:
        return PublishResult(len(files), len(candidates), unchanged, True)

    for source, _relative, values in candidates:
        command = [
            _format_template(part, values, "command") for part in publisher.command
        ]
        try:
            subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise AssetPublicationError(
                f"Upload failed for {source}: {error}"
            ) from error

    for source in files:
        relative = _relative_asset_path(config, source)
        values = _format_values(config, qmd_file, source, publisher)
        assets[relative] = {
            "page": values["page"],
            "sha256": values["hash"],
            "key": values["key"],
            "url": _format_template(publisher.url_template, values, "url_template"),
        }

    _write_manifest(config, publisher, manifest)

    for markdown_path in (
        get_cached_markdown_path(config, qmd_file),
        get_preview_markdown_path(config, qmd_file),
    ):
        if markdown_path is not None and markdown_path.is_file():
            content = markdown_path.read_text(encoding="utf-8")
            markdown_path.write_text(
                apply_published_asset_urls(config, qmd_file, content),
                encoding="utf-8",
            )

    shutil.rmtree(asset_dir)
    return PublishResult(len(files), len(candidates), unchanged, False)
