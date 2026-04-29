"""Build cache management for foliate."""

import json
from pathlib import Path

BUILD_CACHE_FILE = ".build_cache"

# Special cache keys for global dependencies
CONFIG_MTIME_KEY = "__config_mtime__"
TEMPLATES_MTIME_KEY = "__templates_mtime__"


def load_build_cache(cache_file: Path) -> dict:
    """Load the build cache containing file modification times.

    Args:
        cache_file: Path to the cache file

    Returns:
        Dictionary mapping file paths to modification times
    """
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return {}
    return {}


def save_build_cache(cache_file: Path, cache_data: dict) -> None:
    """Save the build cache.

    Args:
        cache_file: Path to the cache file
        cache_data: Dictionary mapping file paths to modification times
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)


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


def _get_existing_mtime(path: Path | None) -> float:
    """Return a filesystem mtime when a path exists, otherwise 0."""
    if path is None:
        return 0.0
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def get_templates_mtime(vault_path: Path) -> float:
    """Get the most recent modification time of all template files.

    Checks both user templates and bundled default templates.

    Args:
        vault_path: Path to the vault directory

    Returns:
        Most recent mtime across all templates, or 0 if none found
    """
    import importlib.resources

    from .templates import DEFAULT_TEMPLATES_PACKAGE, get_user_templates_dir

    max_mtime = 0.0

    # Check user templates, including nested partials/includes.
    user_templates = get_user_templates_dir(vault_path)
    if user_templates.exists():
        for template_file in user_templates.rglob("*.html"):
            max_mtime = max(max_mtime, template_file.stat().st_mtime)

    # Check bundled templates
    try:
        templates_pkg = importlib.resources.files(DEFAULT_TEMPLATES_PACKAGE)
        for item in templates_pkg.iterdir():
            if item.is_file() and item.name.endswith(".html"):
                # For traversable resources, try to get mtime if it's a real file
                try:
                    item_path = Path(str(item))
                    if item_path.exists():
                        max_mtime = max(max_mtime, item_path.stat().st_mtime)
                except (OSError, ValueError):
                    pass
    except (ImportError, TypeError):
        pass

    return max_mtime


def get_global_deps_mtimes(
    config_path: Path | None, vault_path: Path
) -> dict[str, float]:
    """Return current mtimes for build-wide config and template dependencies."""
    mtimes = {TEMPLATES_MTIME_KEY: get_templates_mtime(vault_path)}

    config_mtime = _get_existing_mtime(config_path)
    if config_mtime:
        mtimes[CONFIG_MTIME_KEY] = config_mtime

    return mtimes


def get_global_deps_mtime(config_path: Path | None, vault_path: Path) -> float:
    """Return the newest mtime among build-wide dependencies."""
    return max(get_global_deps_mtimes(config_path, vault_path).values(), default=0.0)


def check_global_deps_changed(
    cache: dict, config_path: Path | None, vault_path: Path
) -> bool:
    """Check if global dependencies (config, templates) have changed.

    Args:
        cache: Build cache dictionary
        config_path: Path to config.toml
        vault_path: Path to the vault directory

    Returns:
        True if config or templates changed since last build
    """
    current_mtimes = get_global_deps_mtimes(config_path, vault_path)
    return any(
        current_mtime > cache.get(cache_key, 0)
        for cache_key, current_mtime in current_mtimes.items()
    )


def update_global_deps_cache(
    cache: dict, config_path: Path | None, vault_path: Path
) -> None:
    """Update cache with current global dependency mtimes.

    Args:
        cache: Build cache dictionary to update
        config_path: Path to config.toml
        vault_path: Path to the vault directory
    """
    cache.update(get_global_deps_mtimes(config_path, vault_path))
