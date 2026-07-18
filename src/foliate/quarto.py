"""Quarto preprocessing for foliate.

Converts .qmd files to cached .md before the main build.
"""

import shutil
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from .config import Config
from .logging import debug
from .quarto_renderer import is_quarto_available, render_qmd

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows falls back to process locking
    fcntl = None  # type: ignore[assignment]


_RENDER_THREAD_LOCK = threading.RLock()
_RENDER_LOCK_DEPTH: ContextVar[int] = ContextVar("quarto_render_lock_depth", default=0)


@contextmanager
def quarto_render_lock(config: Config) -> Iterator[None]:
    """Serialize Quarto and publication work across threads and processes."""
    with _RENDER_THREAD_LOCK:
        depth = _RENDER_LOCK_DEPTH.get()
        if depth:
            token = _RENDER_LOCK_DEPTH.set(depth + 1)
            try:
                yield
            finally:
                _RENDER_LOCK_DEPTH.reset(token)
            return

        lock_path = config.get_cache_dir() / "quarto" / "render.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            token = _RENDER_LOCK_DEPTH.set(1)
            try:
                yield
            finally:
                _RENDER_LOCK_DEPTH.reset(token)
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def is_quarto_preprocessing_available() -> bool:
    """Return whether Quarto preprocessing can run in this environment."""
    return bool(is_quarto_available())


def get_buildable_content_suffixes(config: Config) -> set[str]:
    """Return the content suffixes buildable in the current environment."""
    suffixes = {".md"}
    if config.advanced.quarto_enabled and is_quarto_preprocessing_available():
        suffixes.add(".qmd")
    return suffixes


def get_cached_markdown_path(config: Config, qmd_file: Path) -> Path | None:
    """Return the cached rendered markdown path for a Quarto source file."""
    vault_path = config.vault_path
    if not vault_path:
        return None

    try:
        rel_path = qmd_file.resolve().relative_to(vault_path.resolve())
    except ValueError:
        return None

    return config.get_cache_dir() / "quarto" / "rendered" / rel_path.with_suffix(".md")


def get_preview_markdown_path(config: Config, qmd_file: Path) -> Path | None:
    """Return the Obsidian preview markdown path for a Quarto source file."""
    vault_path = config.vault_path
    if not vault_path:
        return None

    preview_dir = config.advanced.quarto_preview_dir.strip()
    if not preview_dir:
        return None

    try:
        rel_path = qmd_file.resolve().relative_to(vault_path.resolve())
    except ValueError:
        return None

    return vault_path / preview_dir / rel_path.with_suffix(".md")


def get_quarto_asset_dir(config: Config, qmd_file: Path) -> Path | None:
    """Return the generated asset directory for a Quarto source file."""
    vault_path = config.vault_path
    if not vault_path:
        return None

    from .published_assets import get_managed_asset_dir, is_managed_page

    if is_managed_page(qmd_file):
        return get_managed_asset_dir(config, qmd_file)

    try:
        rel_path = qmd_file.resolve().relative_to(vault_path.resolve())
    except ValueError:
        return None

    assets_dir = vault_path.resolve() / "assets" / "quarto"
    parent = rel_path.parent
    if parent == Path("."):
        return assets_dir / qmd_file.stem
    return assets_dir / parent / qmd_file.stem


def _resolve_quarto_python(config: Config) -> str | None:
    """Return the configured interpreter or a vault-local virtualenv Python."""
    if config.advanced.quarto_python:
        return config.advanced.quarto_python

    if config.vault_path is None:
        return None

    virtualenv = config.vault_path / ".venv"
    for candidate in (
        virtualenv / "bin" / "python",
        virtualenv / "Scripts" / "python.exe",
    ):
        if candidate.is_file():
            # Do not resolve the symlink: Python uses its venv path to discover
            # the environment's installed packages.
            return str(candidate.absolute())
    return None


def _is_metadata_line(line: str) -> bool:
    """Return whether a line looks like a Quarto title-block author/date entry.

    Author and date lines emitted under the generated title are short tokens
    without sentence punctuation. Anything longer or sentence-like is treated
    as body prose so a heading that happens to match the filename stem cannot
    swallow real content (e.g. ``# stem`` immediately followed by a paragraph).
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 50:
        return False
    return stripped[-1] not in ".!?:"


def _unescape_outside_code(text: str) -> str:
    """Apply Quarto un-escaping, skipping fenced code blocks.

    Quarto escapes Obsidian wikilink and pipe syntax that foliate needs back
    in raw form, but those same sequences may appear literally inside fenced
    code blocks, where they must be preserved verbatim.
    """
    out: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        if in_fence:
            if stripped.startswith(fence_marker):
                in_fence = False
            out.append(line)
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = True
            fence_marker = stripped[:3]
            out.append(line)
            continue
        line = line.replace(r"\[\[", "[[")
        line = line.replace(r"\]\]", "]]")
        line = line.replace(r"\|", "|")
        line = line.replace("](./assets/", "](/assets/")
        out.append(line)
    return "\n".join(out)


def _clean_rendered_markdown(text: str, qmd_file: Path) -> str:
    """Clean Quarto GFM output for wiki rendering and Obsidian preview."""
    lines = text.splitlines()
    if lines and lines[0] == "---":
        try:
            end = lines.index("---", 1)
        except ValueError:
            end = -1
        if end >= 0:
            body_start = end + 1
            generated_title = [
                f"# {qmd_file.stem}",
            ]
            # Quarto's standalone GFM writer may add title/author/date lines
            # after frontmatter. Foliate already renders the frontmatter title.
            while body_start < len(lines) and lines[body_start] == "":
                body_start += 1
            if body_start < len(lines) and lines[body_start].lower() in {
                title.lower() for title in generated_title
            }:
                body_start += 1
                # Only consume short, metadata-like lines (author/date) so a
                # body paragraph following the generated title is not lost.
                while body_start < len(lines) and _is_metadata_line(lines[body_start]):
                    body_start += 1
                while body_start < len(lines) and lines[body_start] == "":
                    body_start += 1
                lines = lines[: end + 1] + [""] + lines[body_start:]

    cleaned = _unescape_outside_code("\n".join(lines)).rstrip() + "\n"
    return cleaned


def _preview_is_stale(preview_md: Path, cached_md: Path) -> bool:
    """Return whether the Obsidian preview is missing or older than the cache."""
    if not preview_md.exists():
        return True
    return preview_md.stat().st_mtime < cached_md.stat().st_mtime


def _write_preview(
    config: Config, preview_md: Path, rendered_md: Path, qmd_file: Path
) -> None:
    """Write a generated Obsidian preview copy of rendered markdown."""
    base_path = (config.vault_path or qmd_file.parent).resolve()
    try:
        rel_source = qmd_file.resolve().relative_to(base_path)
    except ValueError:
        rel_source = qmd_file

    preview_md.parent.mkdir(parents=True, exist_ok=True)
    content = rendered_md.read_text(encoding="utf-8")
    warning = f"<!-- GENERATED FROM {rel_source.as_posix()}; DO NOT EDIT -->\n\n"
    lines = content.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                insert_at = index + 1
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
                preview_md.write_text(
                    "".join(lines[: index + 1] + ["\n", warning] + lines[insert_at:]),
                    encoding="utf-8",
                )
                return

    preview_md.write_text(warning + content, encoding="utf-8")


def preprocess_quarto(
    config: Config,
    force: bool = False,
    single_file: Path | None = None,
    *,
    validate_published_assets: bool = True,
) -> dict[str, str]:
    """Preprocess .qmd files to cached Markdown using Quarto.

    Args:
        config: Foliate configuration
        force: Force re-render all .qmd files
        single_file: Only process this specific .qmd file (Path object)

    Returns:
        dict mapping .qmd paths to cached rendered .md paths,
        or empty dict if disabled/unavailable
    """
    if not config.advanced.quarto_enabled:
        return {}

    if not is_quarto_available():
        debug("Quarto CLI not found, skipping .qmd preprocessing")
        return {}

    vault_path = config.vault_path
    if not vault_path:
        return {}

    pages_path = vault_path.resolve()
    cache_dir = config.get_cache_dir() / "quarto"
    quarto_python = _resolve_quarto_python(config)

    def _render_source(qmd_file: Path) -> str | None:
        cached_md = get_cached_markdown_path(config, qmd_file)
        if cached_md is None:
            return None

        sibling_md = qmd_file.with_suffix(".md")
        sibling_backup = sibling_md.with_name(f"{sibling_md.name}.foliate-bak")
        # Recover a sibling left stranded by a previous run that crashed between
        # backing the file up and restoring it (e.g. on SIGKILL/power loss).
        if sibling_backup.exists() and not sibling_md.exists():
            sibling_backup.replace(sibling_md)

        # Check if render needed: md doesn't exist or qmd is newer
        needs_render = not cached_md.exists() or (
            qmd_file.stat().st_mtime > cached_md.stat().st_mtime
        )

        if not force and not needs_render:
            from .published_assets import apply_published_asset_urls

            content = cached_md.read_text(encoding="utf-8")
            prepared = apply_published_asset_urls(
                config,
                qmd_file,
                content,
                require_current=validate_published_assets,
            )
            if prepared != content:
                cached_md.write_text(prepared, encoding="utf-8")
            preview_md = get_preview_markdown_path(config, qmd_file)
            if preview_md is not None and _preview_is_stale(preview_md, cached_md):
                _write_preview(config, preview_md, cached_md, qmd_file)
            return str(cached_md)

        # Move existing per-document assets aside rather than deleting them, so
        # a failed render leaves the previous output (and its links) intact.
        asset_dir = get_quarto_asset_dir(config, qmd_file)
        asset_backup: Path | None = None
        if asset_dir is not None and asset_dir.exists():
            asset_backup = asset_dir.with_name(f"{asset_dir.name}.foliate-bak")
            if asset_backup.exists():
                shutil.rmtree(asset_backup)
            asset_dir.replace(asset_backup)

        had_sibling = sibling_md.exists()
        if had_sibling:
            if sibling_backup.exists():
                sibling_backup.unlink()
            sibling_md.replace(sibling_backup)

        result = None
        succeeded = False
        try:
            from .published_assets import (
                apply_published_asset_urls,
                get_managed_asset_root,
                is_managed_page,
                is_published_page,
                load_publisher_config,
            )

            if is_managed_page(qmd_file):
                publisher = load_publisher_config(config)
                render_assets_dir = get_managed_asset_root(config, publisher)
            else:
                render_assets_dir = pages_path / "assets" / "quarto"
            result = render_qmd(
                qmd_file=qmd_file,
                pages_dir=pages_path,
                cache_dir=cache_dir,
                assets_dir=render_assets_dir,
                python=quarto_python,
                verbose=False,
            )
            if not result:
                return None

            cached_md.parent.mkdir(parents=True, exist_ok=True)
            rendered_text = Path(result).read_text(encoding="utf-8")
            cleaned_text = _clean_rendered_markdown(rendered_text, qmd_file)
            cleaned_text = apply_published_asset_urls(
                config,
                qmd_file,
                cleaned_text,
                require_current=validate_published_assets,
            )
            cached_md.write_text(
                cleaned_text,
                encoding="utf-8",
            )

            preview_md = get_preview_markdown_path(config, qmd_file)
            if preview_md is not None:
                _write_preview(config, preview_md, cached_md, qmd_file)

            if (
                validate_published_assets
                and is_managed_page(qmd_file)
                and is_published_page(qmd_file)
                and asset_dir is not None
                and asset_dir.exists()
            ):
                shutil.rmtree(asset_dir)

            succeeded = True
            return str(cached_md)
        finally:
            if result and Path(result).exists():
                Path(result).unlink()
            if had_sibling and sibling_backup.exists():
                sibling_backup.replace(sibling_md)
            if (
                asset_dir is not None
                and asset_backup is not None
                and asset_backup.exists()
            ):
                if succeeded:
                    shutil.rmtree(asset_backup)
                else:
                    # Restore the previous assets the failed render may have
                    # partially overwritten.
                    if asset_dir.exists():
                        shutil.rmtree(asset_dir)
                    asset_backup.replace(asset_dir)

    if single_file:
        # Process single file
        qmd_file = Path(single_file).resolve()
        if not qmd_file.exists():
            debug(f"Quarto source missing, skipping: {qmd_file}")
            return {}

        with quarto_render_lock(config):
            result = _render_source(qmd_file)
        if result:
            return {str(qmd_file): result}
        return {}

    from .build import select_content_sources

    results: dict[str, str] = {}
    selected_sources = select_content_sources(
        pages_path,
        config,
        {".qmd"},
        duplicate_label="Quarto sources",
    )
    for source in selected_sources:
        with quarto_render_lock(config):
            result = _render_source(source.source_file)
        if result:
            results[str(source.source_file)] = result

    return results
