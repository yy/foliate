"""Diagnostics for foliate configuration and templates."""

from __future__ import annotations

from pathlib import Path

import tomllib

from .config import Config
from .templates import get_template_path, list_available_templates

_REQUIRED_TEMPLATES = ("layout.html", "page.html", "index.html")


def _display_path(path: Path, base: Path) -> str:
    """Return a friendly path display, relative when possible."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def run_doctor(start_path: Path | None = None) -> tuple[list[str], list[str], list[str]]:
    """Run diagnostics and return (errors, warnings, ok)."""
    errors: list[str] = []
    warnings: list[str] = []
    ok: list[str] = []

    start_path = start_path or Path.cwd()

    config_path = Config.find_config(start_path)
    if config_path is None:
        errors.append("No .foliate/config.toml found. Run 'foliate init' first.")
        return errors, warnings, ok

    display_config = _display_path(config_path, start_path)

    try:
        config = Config.load(config_path)
    except tomllib.TOMLDecodeError as e:
        errors.append(f"Invalid TOML in {display_config}: {e}")
        return errors, warnings, ok
    except OSError as e:
        errors.append(f"Unable to read {display_config}: {e}")
        return errors, warnings, ok

    ok.append(f"Config loaded: {display_config}")

    vault_path = config.vault_path or config_path.parent.parent

    available_templates = list_available_templates(vault_path)
    missing_templates = [
        name for name in _REQUIRED_TEMPLATES if name not in available_templates
    ]
    if missing_templates:
        errors.append("Missing required templates: " + ", ".join(missing_templates))
    else:
        ok.append("Templates available: " + ", ".join(_REQUIRED_TEMPLATES))

    if config.feed.enabled:
        feed_template = get_template_path("feed.xml", vault_path)
        if feed_template is None:
            errors.append("Feed enabled but feed.xml template not found.")
        else:
            ok.append("Feed template found: feed.xml")

    user_templates = vault_path / ".foliate" / "templates"
    if user_templates.exists():
        ok.append(f"User templates directory: {_display_path(user_templates, start_path)}")
    else:
        ok.append("User templates directory not found (using bundled defaults).")

    user_static = vault_path / ".foliate" / "static"
    if user_static.exists():
        ok.append(f"User static directory: {_display_path(user_static, start_path)}")
    else:
        ok.append("User static directory not found (using bundled defaults).")

    return errors, warnings, ok
