"""Build cache management for foliate."""

import pickle
from pathlib import Path

BUILD_CACHE_FILE = ".build_cache"


def load_build_cache(cache_file: Path) -> dict:
    """Load the build cache containing file modification times.

    Args:
        cache_file: Path to the cache file

    Returns:
        Dictionary mapping file paths to modification times
    """
    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except (pickle.PickleError, OSError, EOFError):
            return {}
    return {}


def save_build_cache(cache_file: Path, cache_data: dict) -> None:
    """Save the build cache.

    Args:
        cache_file: Path to the cache file
        cache_data: Dictionary mapping file paths to modification times
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "wb") as f:
        pickle.dump(cache_data, f)


def needs_rebuild(
    md_file: Path, output_file: Path, cache: dict, force: bool = False
) -> bool:
    """Check if a markdown file needs to be rebuilt.

    Args:
        md_file: Path to the markdown source file
        output_file: Path to the expected output file
        cache: Build cache dictionary
        force: Force rebuild regardless of cache

    Returns:
        True if the file needs to be rebuilt
    """
    if force:
        return True
    if not output_file.exists():
        return True
    md_mtime = md_file.stat().st_mtime
    cache_key = str(md_file)
    if cache_key in cache and cache[cache_key] >= md_mtime:
        return False
    return True
