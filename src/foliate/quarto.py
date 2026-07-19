"""Quarto preprocessing for foliate.

Converts .qmd files to cached .md before the main build.
"""

import threading
from collections.abc import Iterable
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

    try:
        rel_path = qmd_file.resolve().relative_to(vault_path.resolve())
    except ValueError:
        return None

    from .published_assets import get_generated_asset_root

    assets_dir = get_generated_asset_root(config)
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


def _remove_empty_artifact_parents(path: Path, root: Path) -> None:
    """Remove empty artifact directories below a managed root."""
    current = path
    while current != root:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _prune_markdown_artifacts(
    root: Path,
    expected_files: set[Path],
    *,
    require_generated_marker: bool,
) -> None:
    """Remove stale generated Markdown files from a managed artifact tree."""
    if not root.is_dir():
        return

    for artifact in root.rglob("*.md"):
        if artifact in expected_files:
            continue
        if require_generated_marker:
            try:
                content = artifact.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            has_generated_marker = (
                "<!-- GENERATED FROM " in content and "; DO NOT EDIT -->" in content
            )
            if not has_generated_marker:
                continue

        try:
            artifact.unlink()
        except OSError:
            continue
        _remove_empty_artifact_parents(artifact.parent, root)


def _prune_stale_quarto_markdown(
    config: Config,
    source_files: list[Path],
) -> None:
    """Reconcile rendered and preview Markdown with the current QMD inventory."""
    cached_root = config.get_cache_dir() / "quarto" / "rendered"
    expected_cached = {
        cached_path
        for source_file in source_files
        if (cached_path := get_cached_markdown_path(config, source_file)) is not None
    }
    _prune_markdown_artifacts(
        cached_root,
        expected_cached,
        require_generated_marker=False,
    )

    vault_path = config.vault_path
    preview_dir = config.advanced.quarto_preview_dir.strip()
    if not vault_path or not preview_dir:
        return

    preview_root = vault_path / preview_dir
    expected_previews = {
        preview_path
        for source_file in source_files
        if (preview_path := get_preview_markdown_path(config, source_file)) is not None
    }
    _prune_markdown_artifacts(
        preview_root,
        expected_previews,
        require_generated_marker=True,
    )


def preprocess_quarto(
    config: Config,
    force: bool = False,
    single_file: Path | None = None,
    *,
    source_files: Iterable[Path] | None = None,
) -> dict[str, str]:
    """Preprocess .qmd files to cached Markdown using Quarto.

    Args:
        config: Foliate configuration
        force: Force re-render all .qmd files
        single_file: Only process this specific .qmd file (Path object)
        source_files: Optional preselected bulk-mode QMD sources

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

        asset_dir = get_quarto_asset_dir(config, qmd_file)

        # Check if render needed: markdown is missing/newer, or a cached page
        # references generated figures that are absent from the active backend.
        needs_render = not cached_md.exists() or (
            qmd_file.stat().st_mtime > cached_md.stat().st_mtime
        )
        if not needs_render and asset_dir is not None and not asset_dir.exists():
            cached_text = cached_md.read_text(encoding="utf-8")
            needs_render = any(
                prefix in cached_text
                for prefix in ("/assets/quarto/", "/assets/drafts/quarto/")
            )

        if not force and not needs_render:
            preview_md = get_preview_markdown_path(config, qmd_file)
            if preview_md is not None and _preview_is_stale(preview_md, cached_md):
                _write_preview(config, preview_md, cached_md, qmd_file)
            return str(cached_md)

        had_sibling = sibling_md.exists()
        if had_sibling:
            if sibling_backup.exists():
                sibling_backup.unlink()
            sibling_md.replace(sibling_backup)

        result = None
        try:
            from .published_assets import get_generated_asset_root

            render_assets_dir = get_generated_asset_root(config)
            result = render_qmd(
                qmd_file=qmd_file,
                pages_dir=pages_path,
                cache_dir=cache_dir,
                assets_dir=render_assets_dir,
                asset_url_prefix="/assets/quarto",
                python=quarto_python,
                verbose=False,
                refresh_cache=force,
            )
            if not result:
                return None

            cached_md.parent.mkdir(parents=True, exist_ok=True)
            rendered_text = Path(result).read_text(encoding="utf-8")
            cleaned_text = _clean_rendered_markdown(rendered_text, qmd_file)
            cached_md.write_text(
                cleaned_text,
                encoding="utf-8",
            )

            preview_md = get_preview_markdown_path(config, qmd_file)
            if preview_md is not None:
                _write_preview(config, preview_md, cached_md, qmd_file)

            return str(cached_md)
        finally:
            if result and Path(result).exists():
                Path(result).unlink()
            if had_sibling and sibling_backup.exists():
                sibling_backup.replace(sibling_md)

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

    results: dict[str, str] = {}
    if source_files is None:
        from .build import select_content_sources

        selected_sources = select_content_sources(
            pages_path,
            config,
            {".qmd"},
            duplicate_label="Quarto sources",
        )
        source_files = (source.source_file for source in selected_sources)

    source_file_list = [Path(source_file) for source_file in source_files]
    with quarto_render_lock(config):
        _prune_stale_quarto_markdown(config, source_file_list)

    for qmd_file in source_file_list:
        with quarto_render_lock(config):
            result = _render_source(qmd_file)
        if result:
            results[str(qmd_file)] = result

    return results
