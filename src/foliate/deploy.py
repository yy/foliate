"""Deployment functionality for foliate."""

import subprocess
from datetime import datetime
from pathlib import Path

from .config import Config


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

    # Get the most recent source modification time
    source_mtime = _get_newest_source_mtime(config)

    return source_mtime > build_mtime


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
    - Markdown files in the vault (excluding ignored folders and .foliate)
    - config.toml
    - User templates in .foliate/templates

    Args:
        config: The foliate configuration

    Returns:
        Most recent mtime, or 0 if no files found
    """
    from .build import is_path_ignored

    max_mtime = 0.0
    vault_path = config.vault_path

    if not vault_path:
        return max_mtime

    # Check markdown files (excluding ignored folders and .foliate directory)
    for md_file in vault_path.rglob("*.md"):
        # Skip .foliate directory
        try:
            rel_path = md_file.relative_to(vault_path)
            if rel_path.parts and rel_path.parts[0] == ".foliate":
                continue
        except ValueError:
            continue

        # Skip ignored folders
        if is_path_ignored(md_file, vault_path, config.build.ignored_folders):
            continue

        try:
            max_mtime = max(max_mtime, md_file.stat().st_mtime)
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

    return max_mtime


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

    # Pull latest from remote to avoid conflicts when deploying from multiple machines
    if not dry_run:
        info("Pulling latest from remote...")
        pull_result = subprocess.run(
            ["git", "pull", "--rebase", "--autostash"],
            cwd=target,
            capture_output=True,
            text=True,
        )
        if pull_result.returncode != 0:
            # Pull failed - might be a new repo or no remote, which is fine
            if "no tracking information" not in pull_result.stderr.lower():
                warning(f"git pull failed: {pull_result.stderr.strip()}")

    # Build rsync command
    rsync_args = [
        "rsync",
        "-av",
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
        info("Dry run - showing what would be done:\n")

    info(f"Syncing {build_dir} -> {target}")

    # Run rsync (always show output so user sees what's happening)
    rsync_result = subprocess.run(rsync_args)
    if rsync_result.returncode != 0:
        error("rsync failed")
        return False

    # Check for changes in target repo
    diff_result = subprocess.run(
        ["git", "diff", "--quiet"],
        cwd=target,
        capture_output=True,
    )

    # Also check for untracked files
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target,
        capture_output=True,
        text=True,
    )

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

    add_result = subprocess.run(
        ["git", "add", "."],
        cwd=target,
        capture_output=True,
    )
    if add_result.returncode != 0:
        error("git add failed")
        return False

    commit_result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if commit_result.returncode != 0:
        error("git commit failed")
        error(commit_result.stderr)
        return False

    info("Pushing to remote...")

    push_result = subprocess.run(
        ["git", "push"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if push_result.returncode != 0:
        error("git push failed")
        error(push_result.stderr)
        return False

    info("Deploy complete!")
    return True
