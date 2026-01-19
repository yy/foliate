"""Asset handling for foliate."""

import importlib.resources
import shutil
from pathlib import Path
from typing import Optional

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


def copy_directory_incremental(
    src_dir: Path,
    target_dir: Path,
    force_rebuild: bool,
    filter_extensions: Optional[set] = None,
    label: str = "assets",
) -> None:
    """Copy a directory to build output with incremental update support.

    Args:
        src_dir: Source directory to copy from
        target_dir: Target directory to copy to
        force_rebuild: If True, always copy everything
        filter_extensions: Optional set of file extensions to include
        label: Label for logging purposes
    """
    if force_rebuild or not target_dir.exists():
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(src_dir, target_dir)
    else:
        for src_file in src_dir.glob("**/*"):
            if not src_file.is_file():
                continue
            if filter_extensions and src_file.suffix.lower() not in filter_extensions:
                continue
            target_file = target_dir / src_file.relative_to(src_dir)
            if (
                not target_file.exists()
                or src_file.stat().st_mtime > target_file.stat().st_mtime
            ):
                shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
                break


def copy_static_assets(vault_path: Path, build_dir: Path, force_rebuild: bool) -> None:
    """Copy static assets from bundled defaults and user overrides.

    Args:
        vault_path: Path to the vault directory
        build_dir: Path to the build output directory
        force_rebuild: If True, always copy everything
    """
    # Copy bundled static files first
    try:
        static_pkg = importlib.resources.files("foliate.defaults.static")
        bundled_static = build_dir / "static"
        bundled_static.mkdir(parents=True, exist_ok=True)

        for item in static_pkg.iterdir():
            # Skip Python files (like __init__.py)
            if item.is_file() and not item.name.endswith(".py"):
                target = bundled_static / item.name
                if force_rebuild or not target.exists():
                    target.write_bytes(item.read_bytes())
    except (ImportError, TypeError):
        pass

    # Override with user static files if present
    user_static = vault_path / ".foliate" / "static"
    if user_static.exists():
        copy_directory_incremental(
            user_static,
            build_dir / "static",
            force_rebuild,
            label="Static",
        )


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
            label="Assets",
        )
