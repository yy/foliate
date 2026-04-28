"""Command-line interface for foliate."""

from pathlib import Path
from typing import NoReturn

import click

from .assets import robust_rmtree
from .config import Config
from .resources import copy_package_files, read_package_text

# Inline fallback config in case package resources aren't available
_FALLBACK_CONFIG = """\
[site]
name = "My Site"
url = "https://example.com"
author = ""

[build]
ignored_folders = ["_private"]
home_redirect = "about"

[nav]
items = [
    { url = "/about/", label = "About" },
    { url = "/wiki/Home/", label = "Wiki" },
]
"""


def _validate_init_paths(
    foliate_dir: Path,
    config_file: Path,
    templates_dir: Path,
    static_dir: Path,
) -> str | None:
    """Return an init-path conflict message when scaffolding would fail."""
    if foliate_dir.exists() and not foliate_dir.is_dir():
        return ".foliate already exists and is not a directory"
    if config_file.exists() and config_file.is_dir():
        return ".foliate/config.toml already exists and is not a file"
    if templates_dir.exists() and not templates_dir.is_dir():
        return ".foliate/templates already exists and is not a directory"
    if static_dir.exists() and not static_dir.is_dir():
        return ".foliate/static already exists and is not a directory"
    return None


def _exit_with_error(message: str, *, leading_newline: bool = False) -> NoReturn:
    """Print a CLI error message and exit with status 1."""
    prefix = "\n" if leading_newline else ""
    click.echo(f"{prefix}Error: {message}", err=True)
    raise SystemExit(1)


def _load_config_or_exit() -> Config:
    """Load the project config or exit cleanly when it cannot be opened."""
    try:
        return Config.find_and_load()
    except (FileNotFoundError, IsADirectoryError, TypeError, KeyError, ValueError) as e:
        _exit_with_error(str(e))


def get_default_config_content() -> str:
    """Get the default config.toml content from bundled defaults."""
    content = read_package_text("foliate.defaults", "config.toml")
    return content if content else _FALLBACK_CONFIG


def copy_default_templates(target_dir: Path, force: bool = False) -> list[str]:
    """Copy default templates to target directory."""
    return copy_package_files("foliate.defaults.templates", target_dir, force=force)


def copy_default_static(target_dir: Path, force: bool = False) -> list[str]:
    """Copy default static files to target directory."""
    return copy_package_files("foliate.defaults.static", target_dir, force=force)


@click.group()
@click.version_option()
def main():
    """Foliate - Minimal static site generator for markdown vaults."""
    pass


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
def init(force: bool):
    """Initialize a new foliate project."""
    foliate_dir = Path.cwd() / ".foliate"
    config_file = foliate_dir / "config.toml"
    templates_dir = foliate_dir / "templates"
    static_dir = foliate_dir / "static"

    conflict = _validate_init_paths(
        foliate_dir,
        config_file,
        templates_dir,
        static_dir,
    )
    if conflict:
        click.echo(f"Error: {conflict}", err=True)
        raise SystemExit(1)

    if config_file.exists() and not force:
        click.echo("Error: .foliate/config.toml already exists", err=True)
        click.echo("Use --force to overwrite", err=True)
        raise SystemExit(1)

    foliate_dir.mkdir(exist_ok=True)

    # Copy config
    default_config = get_default_config_content()
    config_file.write_text(default_config, encoding="utf-8")
    click.echo(f"Created {config_file}")

    # Copy templates
    templates_created = copy_default_templates(templates_dir, force)
    if templates_created:
        click.echo(f"Created {templates_dir}/ ({len(templates_created)} templates)")

    # Copy static files (CSS)
    static_created = copy_default_static(static_dir, force)
    if static_created:
        click.echo(f"Created {static_dir}/ ({len(static_created)} files)")

    click.echo("\nCustomize your site:")
    click.echo("  - Edit .foliate/config.toml for site settings")
    click.echo("  - Edit .foliate/static/main.css for styling")
    click.echo("  - Edit .foliate/templates/*.html for layout")
    click.echo("\nRun 'foliate build' to build your site")


@main.command()
@click.option("--force", "-f", is_flag=True, help="Force full rebuild")
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be built without writing files",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--serve", "-s", is_flag=True, help="Start local server after build")
@click.option("--port", "-p", default=8000, help="Server port")
def build(force: bool, dry_run: bool, verbose: bool, serve: bool, port: int):
    """Build the static site."""
    from .build import build as do_build
    from .logging import setup_logging

    # Initialize logging based on verbosity
    setup_logging(verbose=verbose)

    config = _load_config_or_exit()

    if dry_run:
        from .status import format_build_dry_run_report, scan_status

        if serve:
            _exit_with_error("--serve cannot be used with --dry-run")

        report = scan_status(config)
        click.echo(
            format_build_dry_run_report(report, force_rebuild=force, verbose=verbose)
        )
        return

    result = do_build(
        config=config,
        force_rebuild=force,
    )

    if result == 0:
        _exit_with_error("No public pages found to build")

    if serve:
        from .resources import start_dev_server

        build_dir = config.get_build_dir()
        try:
            click.echo(f"\nStarting server at http://localhost:{port}")
            click.echo("Press Ctrl+C to stop")
            start_dev_server(build_dir, port, background=False)
        except OSError as e:
            _exit_with_error(str(e), leading_newline=True)
        except KeyboardInterrupt:
            click.echo("\nServer stopped")


@main.command()
@click.option("--port", "-p", default=8000, help="Server port")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def watch(port: int, verbose: bool):
    """Watch for changes and rebuild automatically."""
    from .watch import watch as do_watch

    config = _load_config_or_exit()
    do_watch(config=config, port=port, verbose=verbose)


@main.command()
def clean():
    """Remove build artifacts."""
    start_path = Path.cwd()
    config_path = Config.find_config(start_path)
    foliate_dir = (
        config_path.parent if config_path is not None else start_path / ".foliate"
    )
    build_dir = foliate_dir / "build"
    cache_dir = foliate_dir / "cache"

    cleaned = False

    if build_dir.exists():
        robust_rmtree(build_dir)
        click.echo(f"Removed {build_dir}")
        cleaned = True

    if cache_dir.exists():
        robust_rmtree(cache_dir)
        click.echo(f"Removed {cache_dir}")
        cleaned = True

    if not cleaned:
        click.echo("Nothing to clean")


@main.command()
def doctor():
    """Check configuration and template availability."""
    from .doctor import run_doctor

    errors, warnings, ok = run_doctor()

    for message in errors:
        click.echo(f"Error: {message}", err=True)
    for message in warnings:
        click.echo(f"Warning: {message}", err=True)
    for message in ok:
        click.echo(f"OK: {message}")

    if errors:
        raise SystemExit(1)


@main.command()
@click.option(
    "--verbose", "-v", is_flag=True, help="Show all pages including unchanged"
)
def status(verbose: bool):
    """Show which pages would be built or deployed."""
    from .logging import setup_logging
    from .status import format_status_report, scan_status

    setup_logging(verbose=False)

    config = _load_config_or_exit()
    report = scan_status(config)
    output = format_status_report(report, verbose=verbose)
    click.echo(output)


@main.command()
@click.option(
    "--dry-run", "-n", is_flag=True, help="Show what would be done without executing"
)
@click.option("--message", "-m", default=None, help="Custom commit message")
@click.option("--build", "-b", is_flag=True, help="Build site before deploying")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def deploy(dry_run: bool, message: str, build: bool, verbose: bool):
    """Deploy built site to configured target."""
    from .deploy import deploy_github_pages

    config = _load_config_or_exit()

    if config.resolve_deploy_target() is None:
        click.echo("Error: No deploy target configured", err=True)
        click.echo("Add [deploy] section to .foliate/config.toml", err=True)
        raise SystemExit(1)

    success = deploy_github_pages(
        config, dry_run=dry_run, message=message, build_first=build, verbose=verbose
    )
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
