"""Utilities for working with package resources and paths.

Provides a consistent interface for reading files from Python packages,
with proper error handling for missing resources.
"""

import importlib.resources
import os
from collections.abc import Iterator
from pathlib import Path


def expand_path(path: str) -> str:
    """Expand user home directory (~) in a path.

    Args:
        path: Path string that may contain ~

    Returns:
        Expanded path string
    """
    return os.path.expanduser(path) if path else path


def read_package_text(package: str, filename: str) -> str | None:
    """Read text content from a package resource.

    Args:
        package: Package name (e.g., "foliate.defaults")
        filename: Name of the file to read

    Returns:
        File contents as string, or None if not found
    """
    try:
        pkg = importlib.resources.files(package)
        resource = pkg.joinpath(filename)
        if resource.is_file():
            return resource.read_text(encoding="utf-8")
    except (TypeError, FileNotFoundError):
        pass
    return None


def read_package_bytes(package: str, filename: str) -> bytes | None:
    """Read binary content from a package resource.

    Args:
        package: Package name (e.g., "foliate.defaults.static")
        filename: Name of the file to read

    Returns:
        File contents as bytes, or None if not found
    """
    try:
        pkg = importlib.resources.files(package)
        resource = pkg.joinpath(filename)
        if resource.is_file():
            return resource.read_bytes()
    except (TypeError, FileNotFoundError):
        pass
    return None


def iter_package_files(
    package: str, suffix: str | None = None, exclude_python: bool = True
) -> Iterator[tuple[str, bool]]:
    """Iterate over files in a package.

    Args:
        package: Package name (e.g., "foliate.defaults.templates")
        suffix: Optional suffix to filter by (e.g., ".html")
        exclude_python: If True, skip .py files (default: True)

    Yields:
        Tuples of (filename, is_file) for each item in the package
    """
    try:
        pkg = importlib.resources.files(package)
        for item in pkg.iterdir():
            if not item.is_file():
                continue
            if exclude_python and item.name.endswith(".py"):
                continue
            if suffix and not item.name.endswith(suffix):
                continue
            yield item.name, True
    except (TypeError, FileNotFoundError, ImportError):
        pass


def copy_package_files(
    package: str,
    target_dir: Path,
    suffix: str | None = None,
    force: bool = False,
) -> list[str]:
    """Copy files from a package to a target directory.

    Args:
        package: Package name (e.g., "foliate.defaults.templates")
        target_dir: Directory to copy files to
        suffix: Optional suffix to filter by (e.g., ".html")
        force: If True, overwrite existing files

    Returns:
        List of created file paths
    """
    created = []
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        pkg = importlib.resources.files(package)
        for item in pkg.iterdir():
            if not item.is_file():
                continue
            if item.name.endswith(".py"):
                continue
            if suffix and not item.name.endswith(suffix):
                continue

            target_file = target_dir / item.name
            if force or not target_file.exists():
                # Use bytes for binary safety
                target_file.write_bytes(item.read_bytes())
                created.append(str(target_file))
    except (TypeError, FileNotFoundError, ImportError):
        pass

    return created


def get_package_file_path(package: str, filename: str) -> Path | None:
    """Get a Path-like object for a package resource.

    Note: For zipped packages, this may not be a real filesystem path.

    Args:
        package: Package name
        filename: Name of the file

    Returns:
        Path to the resource, or None if not found
    """
    try:
        pkg = importlib.resources.files(package)
        resource = pkg.joinpath(filename)
        if resource.is_file():
            return Path(str(resource))
    except (TypeError, FileNotFoundError):
        pass
    return None


def start_dev_server(
    build_dir: Path,
    port: int = 8000,
    background: bool = False,
):
    """Start a development HTTP server.

    Args:
        build_dir: Directory to serve files from
        port: Port number (default: 8000)
        background: If True, run in background and return Popen object.
                   If False, run blocking until interrupted.

    Returns:
        subprocess.Popen if background=True, None otherwise
    """
    import subprocess
    import sys

    cmd = [sys.executable, "-m", "http.server", str(port)]

    if background:
        return subprocess.Popen(
            cmd,
            cwd=str(build_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.run(cmd, cwd=str(build_dir))
