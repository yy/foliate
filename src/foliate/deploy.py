"""Deployment functionality for foliate."""

import subprocess
from datetime import datetime
from pathlib import Path

import click

from .config import Config


def deploy_github_pages(
    config: Config, dry_run: bool = False, message: str | None = None
) -> bool:
    """Deploy build to GitHub Pages repository.

    Args:
        config: The foliate configuration
        dry_run: If True, show what would be done without executing
        message: Custom commit message (default: auto-generated)

    Returns:
        True if deployment succeeded, False otherwise
    """
    build_dir = config.get_build_dir()
    target = Path(config.deploy.target)

    # Resolve relative paths relative to vault_path
    if not target.is_absolute() and config.vault_path:
        target = (config.vault_path / target).resolve()

    # Validate build directory exists
    if not build_dir.exists():
        click.echo(f"Error: Build directory not found: {build_dir}", err=True)
        click.echo("Run 'foliate build' first", err=True)
        return False

    # Validate target exists and is a git repo
    if not target.exists():
        click.echo(f"Error: Deploy target not found: {target}", err=True)
        return False

    git_dir = target / ".git"
    if not git_dir.exists():
        click.echo(f"Error: Deploy target is not a git repository: {target}", err=True)
        return False

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
        click.echo("Dry run - showing what would be done:\n")

    click.echo(f"Syncing {build_dir} -> {target}")

    # Run rsync (always show output so user sees what's happening)
    result = subprocess.run(rsync_args)
    if result.returncode != 0:
        click.echo("Error: rsync failed", err=True)
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
        click.echo("No changes to deploy")
        return True

    # Generate commit message
    if message is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Deploy: {timestamp}"

    if dry_run:
        click.echo(f"\nWould commit with message: {message}")
        click.echo("Would push to remote")
        return True

    # Git add, commit, push
    click.echo(f"Committing: {message}")

    add_result = subprocess.run(
        ["git", "add", "."],
        cwd=target,
        capture_output=True,
    )
    if add_result.returncode != 0:
        click.echo("Error: git add failed", err=True)
        return False

    commit_result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if commit_result.returncode != 0:
        click.echo("Error: git commit failed", err=True)
        click.echo(commit_result.stderr, err=True)
        return False

    click.echo("Pushing to remote...")

    push_result = subprocess.run(
        ["git", "push"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if push_result.returncode != 0:
        click.echo("Error: git push failed", err=True)
        click.echo(push_result.stderr, err=True)
        return False

    click.echo("Deploy complete!")
    return True
