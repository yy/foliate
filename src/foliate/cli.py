"""Command-line interface for foliate."""

import shutil
import subprocess
import sys
from pathlib import Path

import click

from .config import Config


def get_default_config_content() -> str:
    """Get the default config.toml content from bundled defaults."""
    import importlib.resources

    try:
        config_file = importlib.resources.files("foliate.defaults").joinpath(
            "config.toml"
        )
        return config_file.read_text(encoding="utf-8")
    except (TypeError, FileNotFoundError):
        # Fallback to inline default
        return """\
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


@click.group()
@click.version_option()
def main():
    """Foliate - Minimal static site generator for markdown vaults."""
    pass


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config")
def init(force: bool):
    """Initialize a new foliate project."""
    foliate_dir = Path.cwd() / ".foliate"
    config_file = foliate_dir / "config.toml"

    if config_file.exists() and not force:
        click.echo("Error: .foliate/config.toml already exists", err=True)
        click.echo("Use --force to overwrite", err=True)
        raise SystemExit(1)

    foliate_dir.mkdir(exist_ok=True)

    default_config = get_default_config_content()
    config_file.write_text(default_config)
    click.echo(f"Created {config_file}")
    click.echo("Run 'foliate build' to build your site")


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
        build_dir = config.get_build_dir()
        click.echo(f"\nStarting server at http://localhost:{port}")
        click.echo("Press Ctrl+C to stop")
        try:
            subprocess.run(
                [sys.executable, "-m", "http.server", str(port)],
                cwd=str(build_dir),
            )
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


if __name__ == "__main__":
    main()
