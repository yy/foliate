"""Command-line interface for foliate."""

import shutil
from pathlib import Path

import click

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


def get_default_config_content() -> str:
    """Get the default config.toml content from bundled defaults."""
    content = read_package_text("foliate.defaults", "config.toml")
    return content if content else _FALLBACK_CONFIG


def copy_default_templates(target_dir: Path, force: bool = False) -> list[str]:
    """Copy default templates to target directory."""
    return copy_package_files(
        "foliate.defaults.templates", target_dir, suffix=".html", force=force
    )


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

    if config_file.exists() and not force:
        click.echo("Error: .foliate/config.toml already exists", err=True)
        click.echo("Use --force to overwrite", err=True)
        raise SystemExit(1)

    foliate_dir.mkdir(exist_ok=True)

    # Copy config
    default_config = get_default_config_content()
    config_file.write_text(default_config)
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
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--serve", "-s", is_flag=True, help="Start local server after build")
@click.option("--port", "-p", default=8000, help="Server port")
def build(force: bool, verbose: bool, serve: bool, port: int):
    """Build the static site."""
    from .build import build as do_build

    try:
        config = Config.find_and_load()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    result = do_build(
        config=config,
        force_rebuild=force,
        verbose=verbose,
    )

    if result == 0:
        click.echo("No public pages found to build", err=True)
        raise SystemExit(1)

    if serve:
        from .resources import start_dev_server

        build_dir = config.get_build_dir()
        click.echo(f"\nStarting server at http://localhost:{port}")
        click.echo("Press Ctrl+C to stop")
        try:
            start_dev_server(build_dir, port, background=False)
        except KeyboardInterrupt:
            click.echo("\nServer stopped")


@main.command()
@click.option("--port", "-p", default=8000, help="Server port")
def watch(port: int):
    """Watch for changes and rebuild automatically."""
    from .watch import watch as do_watch

    try:
        config = Config.find_and_load()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    do_watch(config=config, port=port)


@main.command()
def clean():
    """Remove build artifacts."""
    foliate_dir = Path.cwd() / ".foliate"
    build_dir = foliate_dir / "build"
    cache_dir = foliate_dir / "cache"

    cleaned = False

    if build_dir.exists():
        shutil.rmtree(build_dir)
        click.echo(f"Removed {build_dir}")
        cleaned = True

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        click.echo(f"Removed {cache_dir}")
        cleaned = True

    if not cleaned:
        click.echo("Nothing to clean")


@main.command()
@click.option(
    "--dry-run", "-n", is_flag=True, help="Show what would be done without executing"
)
@click.option("--message", "-m", default=None, help="Custom commit message")
@click.option("--build", "-b", is_flag=True, help="Build site before deploying")
def deploy(dry_run: bool, message: str, build: bool):
    """Deploy built site to configured target."""
    from .deploy import deploy_github_pages

    try:
        config = Config.find_and_load()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if not config.deploy.target:
        click.echo("Error: No deploy target configured", err=True)
        click.echo("Add [deploy] section to .foliate/config.toml", err=True)
        raise SystemExit(1)

    success = deploy_github_pages(
        config, dry_run=dry_run, message=message, build_first=build
    )
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
