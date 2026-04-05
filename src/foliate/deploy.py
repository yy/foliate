"""Deployment functionality for foliate."""

import subprocess
from datetime import datetime
from pathlib import Path

from .cache import BUILD_CACHE_FILE, load_build_cache
from .config import Config


def _dry_run_has_rsync_changes(rsync_stdout: str) -> bool:
    """Return True when rsync --dry-run output indicates file changes."""
    if not rsync_stdout:
        return False

    noise_prefixes = (
        "sending incremental file list",
        "Transfer starting:",
        "sent ",
        "total size is ",
        "created directory ",
    )
    for line in rsync_stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "./":
            continue
        if any(stripped.startswith(prefix) for prefix in noise_prefixes):
            continue
        return True

    return False


def _files_have_same_contents(source: Path, target: Path) -> bool:
    """Return True when two files contain identical bytes."""
    if source.stat().st_size != target.stat().st_size:
        return False

    chunk_size = 8192
    with source.open("rb") as source_handle, target.open("rb") as target_handle:
        while True:
            source_chunk = source_handle.read(chunk_size)
            target_chunk = target_handle.read(chunk_size)
            if source_chunk != target_chunk:
                return False
            if not source_chunk:
                return True


def _dry_run_trees_match(
    build_dir: Path, target_dir: Path, exclude_patterns: list[str]
) -> bool | None:
    """Return whether build and target trees already match for deploy purposes.

    Ignores `.git` metadata and directory mtimes so dry-run deploy checks do not
    depend on rsync for identical-content comparisons.
    """
    literal_exclude_names: set[str] = set()
    literal_exclude_paths: set[tuple[str, ...]] = set()

    for pattern in exclude_patterns:
        if any(char in pattern for char in "*?[]{}!"):
            return None
        normalized = pattern.strip("/")
        if not normalized:
            return None
        parts = tuple(Path(normalized).parts)
        if len(parts) == 1:
            literal_exclude_names.add(parts[0])
        else:
            literal_exclude_paths.add(parts)

    def is_ignored(rel_path: Path) -> bool:
        return (
            ".git" in rel_path.parts
            or rel_path.name in literal_exclude_names
            or rel_path.parts in literal_exclude_paths
        )

    def collect_entries(root: Path) -> dict[Path, str] | None:
        root_entries: dict[Path, str] = {}
        try:
            for path in root.rglob("*"):
                rel_path = path.relative_to(root)
                if is_ignored(rel_path):
                    continue
                if path.is_symlink():
                    return None
                if path.is_dir():
                    root_entries[rel_path] = "dir"
                elif path.is_file():
                    root_entries[rel_path] = "file"
                else:
                    return None
        except OSError:
            return None
        return root_entries

    build_entries = collect_entries(build_dir)
    target_entries = collect_entries(target_dir)
    if build_entries is None or target_entries is None:
        return None
    if build_entries != target_entries:
        return False

    for rel_path, entry_type in build_entries.items():
        if entry_type != "file":
            continue
        try:
            if not _files_have_same_contents(build_dir / rel_path, target_dir / rel_path):
                return False
        except OSError:
            return None

    return True


def is_build_stale(config: Config) -> bool | None:
    """Check if the build directory is stale (source files modified after build).

    Compares the most recent modification time of source files (markdown, config,
    templates) against the most recent modification time in the build directory.

    Args:
        config: The foliate configuration

    Returns:
        True if build is stale, False if up-to-date, None if can't determine
    """
    if not config.vault_path:
        return None

    build_dir = config.get_build_dir()
    if not build_dir.exists():
        return None

    # Get the most recent modification time in the build directory
    build_mtime = _get_newest_mtime_in_dir(build_dir)
    if build_mtime == 0:
        return None

    cache_file = config.get_cache_dir() / BUILD_CACHE_FILE
    build_cache = load_build_cache(cache_file)
    if build_cache and _did_public_source_set_change(config, build_cache):
        return True

    # Get the most recent source modification time
    source_mtime = _get_newest_source_mtime(config)

    return source_mtime > build_mtime


def _collect_public_source_paths(config: Config) -> set[str]:
    """Return the current set of public markdown source files in the vault."""
    from .build import select_content_sources
    from .markdown_utils import parse_markdown_file
    from .quarto import is_quarto_preprocessing_available

    vault_path = config.vault_path
    if not vault_path:
        return set()

    allowed_suffixes = {".md"}
    if config.advanced.quarto_enabled and is_quarto_preprocessing_available():
        allowed_suffixes.add(".qmd")

    public_sources: set[str] = set()
    selected_sources = select_content_sources(vault_path, config, allowed_suffixes)

    for source in selected_sources:
        meta, _ = parse_markdown_file(source.source_file)
        if bool(meta.get("public", False)):
            cache_source = source.source_file
            # Quarto sources are cached under their rendered .md path after
            # preprocessing, so compare using the same normalized key format.
            if cache_source.suffix.lower() == ".qmd":
                cache_source = cache_source.with_suffix(".md")
            public_sources.add(str(cache_source))

    return public_sources


def _did_public_source_set_change(config: Config, build_cache: dict) -> bool:
    """Return True when the set of public source files changed since build.

    The build cache keys are the absolute paths of public source files from the
    last build. Compare those keys with the current public markdown sources so
    the stale check catches both deleted pages and newly added/imported public
    pages whose mtimes may predate the last build.
    """
    from .cache import CONFIG_MTIME_KEY, TEMPLATES_MTIME_KEY

    cached_sources = {
        path
        for path in build_cache
        if path not in {CONFIG_MTIME_KEY, TEMPLATES_MTIME_KEY}
    }
    current_sources = _collect_public_source_paths(config)

    return cached_sources != current_sources


def _is_benign_pull_failure(stderr: str) -> bool:
    """Allow deployment to continue when git pull cannot run harmlessly."""
    normalized = stderr.lower()
    benign_messages = (
        "no tracking information",
        "no upstream configured",
        "there is no tracking information",
    )
    return any(message in normalized for message in benign_messages)


def _get_newest_mtime_in_dir(directory: Path) -> float:
    """Get the most recent modification time of any file in a directory.

    Args:
        directory: Directory to scan

    Returns:
        Most recent mtime, or 0 if no files found
    """
    max_mtime = 0.0
    for file in directory.rglob("*"):
        if file.is_file():
            try:
                max_mtime = max(max_mtime, file.stat().st_mtime)
            except OSError:
                pass
    return max_mtime


def _get_newest_source_mtime(config: Config) -> float:
    """Get the most recent modification time of any source file.

    Source files include:
    - Markdown/Quarto files in the vault (excluding ignored folders and .foliate)
    - User assets in assets/
    - config.toml
    - User templates in .foliate/templates
    - User static files in .foliate/static

    Args:
        config: The foliate configuration

    Returns:
        Most recent mtime, or 0 if no files found
    """
    from .assets import SUPPORTED_ASSET_EXTENSIONS
    from .build import is_path_ignored, iter_source_files

    max_mtime = 0.0
    vault_path = config.vault_path

    if not vault_path:
        return max_mtime

    # Check markdown and quarto files (excluding ignored folders and .foliate directory)
    for source_file in iter_source_files(vault_path, {".md", ".qmd"}):
        # Skip .foliate directory
        try:
            rel_path = source_file.relative_to(vault_path)
            if rel_path.parts and rel_path.parts[0] == ".foliate":
                continue
        except ValueError:
            continue

        # Skip ignored folders
        if is_path_ignored(source_file, vault_path, config.build.ignored_folders):
            continue

        try:
            max_mtime = max(max_mtime, source_file.stat().st_mtime)
        except OSError:
            pass

    # Check user assets
    assets_dir = vault_path / "assets"
    if assets_dir.exists():
        for asset_file in assets_dir.rglob("*"):
            if not asset_file.is_file():
                continue
            if asset_file.suffix.lower() not in SUPPORTED_ASSET_EXTENSIONS:
                continue
            try:
                max_mtime = max(max_mtime, asset_file.stat().st_mtime)
            except OSError:
                pass

    # Check config.toml
    config_file = vault_path / ".foliate" / "config.toml"
    if config_file.exists():
        try:
            max_mtime = max(max_mtime, config_file.stat().st_mtime)
        except OSError:
            pass

    # Check user templates
    templates_dir = vault_path / ".foliate" / "templates"
    if templates_dir.exists():
        for template_file in templates_dir.rglob("*"):
            if template_file.is_file():
                try:
                    max_mtime = max(max_mtime, template_file.stat().st_mtime)
                except OSError:
                    pass

    # Check user static files
    static_dir = vault_path / ".foliate" / "static"
    if static_dir.exists():
        for static_file in static_dir.rglob("*"):
            if static_file.is_file():
                try:
                    max_mtime = max(max_mtime, static_file.stat().st_mtime)
                except OSError:
                    pass

    return max_mtime


def _run_command(args: list[str], error_label: str, **kwargs):
    """Run a subprocess command and convert OS errors into deploy failures."""
    from .logging import error

    try:
        return subprocess.run(args, **kwargs)
    except OSError as exc:
        error(f"{error_label}: {exc}")
        return None


def deploy_github_pages(
    config: Config,
    dry_run: bool = False,
    message: str | None = None,
    build_first: bool = False,
    verbose: bool = False,
) -> bool:
    """Deploy build to GitHub Pages repository.

    Args:
        config: The foliate configuration
        dry_run: If True, show what would be done without executing
        message: Custom commit message (default: auto-generated)
        build_first: If True, run build before deploying
        verbose: Enable verbose output

    Returns:
        True if deployment succeeded, False otherwise
    """
    from .logging import error, info, setup_logging, warning

    # Initialize logging
    setup_logging(verbose=verbose)

    # Run build first if requested
    if build_first:
        from .build import build as do_build

        info("Building site first...")
        result = do_build(config=config, force_rebuild=False)
        if result == 0:
            error("No public pages to deploy")
            return False
        info(f"Built {result} pages\n")

    build_dir = config.get_build_dir()
    target = Path(config.deploy.target)

    # Resolve relative paths relative to vault_path
    if not target.is_absolute() and config.vault_path:
        target = (config.vault_path / target).resolve()

    # Validate build directory exists
    if not build_dir.exists():
        error(f"Build directory not found: {build_dir}")
        error("Run 'foliate build' first")
        return False

    # Warn if build is stale (skip if we just built)
    if not build_first:
        stale = is_build_stale(config)
        if stale:
            warning(
                "Build may be stale. Source files have been modified "
                "since the last build."
            )
            warning(
                "Consider running 'foliate build' or 'foliate deploy --build' first."
            )

    # Validate target exists and is a git repo
    if not target.exists():
        error(f"Deploy target not found: {target}")
        return False

    git_dir = target / ".git"
    if not git_dir.exists():
        error(f"Deploy target is not a git repository: {target}")
        return False

    if dry_run:
        trees_match = _dry_run_trees_match(build_dir, target, config.deploy.exclude)
        if trees_match:
            info("No changes to deploy")
            return True

    # Pull latest from remote to avoid conflicts when deploying from multiple machines
    if not dry_run:
        info("Pulling latest from remote...")
        pull_result = _run_command(
            ["git", "pull", "--rebase", "--autostash"],
            "git pull failed",
            cwd=target,
            capture_output=True,
            text=True,
        )
        if pull_result is None:
            return False
        if pull_result.returncode != 0:
            stderr = pull_result.stderr.strip()
            if _is_benign_pull_failure(stderr):
                warning(f"git pull skipped: {stderr}")
            else:
                error(f"git pull failed: {stderr}")
                return False

    # Build rsync command
    rsync_args = [
        "rsync",
        "-av",
        # Compare file contents, not just mtimes, so rebuilds that produce
        # identical HTML do not create noisy deploy previews or no-op syncs.
        "--checksum",
        "--delete",
        "--exclude=.git",  # Preserve target's git repo
    ]

    # Add configured excludes
    for exclude in config.deploy.exclude:
        rsync_args.append(f"--exclude={exclude}")

    # Source must end with / to copy contents, not directory itself
    rsync_args.append(f"{build_dir}/")
    rsync_args.append(f"{target}/")

    if dry_run:
        rsync_args.insert(1, "--dry-run")
        rsync_args.insert(2, "--itemize-changes")
        info("Dry run - showing what would be done:\n")

    info(f"Syncing {build_dir} -> {target}")

    # Run rsync
    if dry_run:
        rsync_result = _run_command(
            rsync_args,
            "rsync failed",
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        # Always show output in non-dry-run so user sees what's happening.
        rsync_result = _run_command(
            rsync_args,
            "rsync failed",
            encoding="utf-8",
            errors="replace",
        )

    if rsync_result is None:
        return False

    if rsync_result.returncode != 0:
        error("rsync failed")
        return False

    if dry_run:
        if rsync_result.stdout:
            info(rsync_result.stdout.rstrip())
        has_changes = _dry_run_has_rsync_changes(rsync_result.stdout)
        if not has_changes:
            info("No changes to deploy")
            return True

    else:
        # Check for changes in target repo
        diff_result = _run_command(
            ["git", "diff", "--quiet"],
            "git diff failed",
            cwd=target,
            capture_output=True,
        )

        # Also check for untracked files
        status_result = _run_command(
            ["git", "status", "--porcelain"],
            "git status failed",
            cwd=target,
            capture_output=True,
            text=True,
        )
        if diff_result is None or status_result is None:
            return False

        has_changes = diff_result.returncode != 0 or bool(status_result.stdout.strip())

    if not has_changes:
        info("No changes to deploy")
        return True

    # Generate commit message
    if message is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Deploy: {timestamp}"

    if dry_run:
        info(f"\nWould commit with message: {message}")
        info("Would push to remote")
        return True

    # Git add, commit, push
    info(f"Committing: {message}")

    add_result = _run_command(
        ["git", "add", "."],
        "git add failed",
        cwd=target,
        capture_output=True,
    )
    if add_result is None:
        return False
    if add_result.returncode != 0:
        error("git add failed")
        return False

    commit_result = _run_command(
        ["git", "commit", "-m", message],
        "git commit failed",
        cwd=target,
        capture_output=True,
        text=True,
    )
    if commit_result is None:
        return False
    if commit_result.returncode != 0:
        error("git commit failed")
        error(commit_result.stderr)
        return False

    info("Pushing to remote...")

    push_result = _run_command(
        ["git", "push"],
        "git push failed",
        cwd=target,
        capture_output=True,
        text=True,
    )
    if push_result is None:
        return False
    if push_result.returncode != 0:
        error("git push failed")
        error(push_result.stderr)
        return False

    info("Deploy complete!")
    return True
