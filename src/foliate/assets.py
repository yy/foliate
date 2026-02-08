"""Asset handling for foliate."""

import shutil
import time
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
    filter_extensions: set | None = None,
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
        shutil.copytree(src_dir, target_dir)
        return

    source_files: set[Path] = set()
    needs_refresh = False

    for src_file in src_dir.glob("**/*"):
        if not src_file.is_file():
            continue
        if filter_extensions and src_file.suffix.lower() not in filter_extensions:
            continue

        rel_path = src_file.relative_to(src_dir)
        source_files.add(rel_path)

        target_file = target_dir / rel_path
        if (
            not target_file.exists()
            or src_file.stat().st_mtime > target_file.stat().st_mtime
        ):
            needs_refresh = True
            break

    if not needs_refresh:
        for target_file in target_dir.glob("**/*"):
            if not target_file.is_file():
                continue
            if (
                filter_extensions
                and target_file.suffix.lower() not in filter_extensions
            ):
                continue
            rel_path = target_file.relative_to(target_dir)
            if rel_path not in source_files:
                needs_refresh = True
                break

    if needs_refresh:
        robust_rmtree(target_dir)
        shutil.copytree(src_dir, target_dir)


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
    if user_static.exists():
        shutil.copytree(user_static, bundled_static, dirs_exist_ok=True)


def copy_user_assets(vault_path: Path, build_dir: Path, force_rebuild: bool) -> None:
    """Copy user assets from vault to build directory.

    Args:
        vault_path: Path to the vault directory
        build_dir: Path to the build output directory
        force_rebuild: If True, always copy everything
    """
    assets_src = vault_path / "assets"
    if assets_src.exists():
        copy_directory_incremental(
            assets_src,
            build_dir / "assets",
            force_rebuild,
            filter_extensions=SUPPORTED_ASSET_EXTENSIONS,
        )
