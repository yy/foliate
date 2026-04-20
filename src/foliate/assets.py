"""Asset handling for foliate."""

import shutil
import time
from collections.abc import Iterator
from pathlib import Path

# Supported asset file extensions
SUPPORTED_ASSET_EXTENSIONS = {
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".bmp",
    ".ico",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".bib",
    # Media
    ".mp4",
    ".mp3",
    ".wav",
    ".avi",
    ".mov",
    # Other
    ".zip",
    ".tar",
    ".gz",
}


def _should_copy_file(path: Path, filter_extensions: set[str] | None) -> bool:
    """Return whether a file should be copied under the active filter."""
    return not filter_extensions or path.suffix.lower() in filter_extensions


def _copy_directory(
    src_dir: Path, target_dir: Path, filter_extensions: set[str] | None = None
) -> None:
    """Copy a directory tree while honoring optional extension filtering."""

    def _ignore(directory: str, entries: list[str]) -> list[str]:
        directory_path = Path(directory)
        return [
            entry
            for entry in entries
            if (directory_path / entry).is_file()
            and not _should_copy_file(directory_path / entry, filter_extensions)
        ]

    shutil.copytree(src_dir, target_dir, ignore=_ignore)


def _iter_filtered_files(
    root_dir: Path,
    filter_extensions: set[str] | None = None,
) -> Iterator[Path]:
    """Yield regular files below a directory under the active filter."""
    for path in root_dir.glob("**/*"):
        if path.is_file() and _should_copy_file(path, filter_extensions):
            yield path


def _source_tree_needs_refresh(
    src_dir: Path,
    target_dir: Path,
    filter_extensions: set[str] | None = None,
) -> tuple[bool, set[Path]]:
    """Return whether source changes require a refresh and the expected files."""
    source_files: set[Path] = set()

    for src_file in _iter_filtered_files(src_dir, filter_extensions):
        rel_path = src_file.relative_to(src_dir)
        source_files.add(rel_path)

        target_file = target_dir / rel_path
        if (
            not target_file.exists()
            or src_file.stat().st_mtime > target_file.stat().st_mtime
        ):
            return True, source_files

    return False, source_files


def _target_tree_needs_refresh(
    target_dir: Path,
    source_files: set[Path],
    filter_extensions: set[str] | None = None,
) -> bool:
    """Return whether target-only or unsupported files require a refresh."""
    for target_file in target_dir.glob("**/*"):
        if not target_file.is_file():
            continue
        rel_path = target_file.relative_to(target_dir)
        if not _should_copy_file(target_file, filter_extensions):
            return True
        if rel_path not in source_files:
            return True
    return False


def _directory_copy_needs_refresh(
    src_dir: Path,
    target_dir: Path,
    filter_extensions: set[str] | None = None,
) -> bool:
    """Return whether incremental copying should rebuild the target tree."""
    source_needs_refresh, source_files = _source_tree_needs_refresh(
        src_dir,
        target_dir,
        filter_extensions,
    )
    if source_needs_refresh:
        return True
    return _target_tree_needs_refresh(target_dir, source_files, filter_extensions)


def robust_rmtree(path: Path, retries: int = 3, delay: float = 0.1) -> None:
    """Remove a directory tree with retry logic for macOS file descriptor races."""
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                raise


def copy_directory_incremental(
    src_dir: Path,
    target_dir: Path,
    force_rebuild: bool,
    filter_extensions: set[str] | None = None,
) -> None:
    """Copy a directory to build output with incremental update support.

    Args:
        src_dir: Source directory to copy from
        target_dir: Target directory to copy to
        force_rebuild: If True, always copy everything
        filter_extensions: Optional set of file extensions to include
    """
    if force_rebuild or not target_dir.exists():
        if target_dir.exists():
            robust_rmtree(target_dir)
        _copy_directory(src_dir, target_dir, filter_extensions)
        return

    if _directory_copy_needs_refresh(src_dir, target_dir, filter_extensions):
        robust_rmtree(target_dir)
        _copy_directory(src_dir, target_dir, filter_extensions)


def copy_static_assets(vault_path: Path, build_dir: Path, force_rebuild: bool) -> None:
    """Copy static assets from bundled defaults and user overrides.

    Args:
        vault_path: Path to the vault directory
        build_dir: Path to the build output directory
        force_rebuild: If True, always copy everything
    """
    from .resources import copy_package_files

    # Rebuild static directory from scratch each run so user overrides
    # cannot remove bundled defaults and deleted overrides don't linger.
    bundled_static = build_dir / "static"
    if bundled_static.exists():
        robust_rmtree(bundled_static)
    copy_package_files("foliate.defaults.static", bundled_static, force=True)

    # Override with user static files if present
    user_static = vault_path / ".foliate" / "static"
    if user_static.is_dir():
        shutil.copytree(user_static, bundled_static, dirs_exist_ok=True)


def copy_user_assets(vault_path: Path, build_dir: Path, force_rebuild: bool) -> None:
    """Copy user assets from vault to build directory.

    Args:
        vault_path: Path to the vault directory
        build_dir: Path to the build output directory
        force_rebuild: If True, always copy everything
    """
    assets_src = vault_path / "assets"
    if assets_src.is_dir():
        copy_directory_incremental(
            assets_src,
            build_dir / "assets",
            force_rebuild,
            filter_extensions=SUPPORTED_ASSET_EXTENSIONS,
        )
