"""Diagnostics for foliate configuration and templates."""

from __future__ import annotations

import tomllib
from pathlib import Path

from .assets import get_user_static_dir
from .config import Config
from .templates import (
    get_template_path,
    get_user_templates_dir,
    list_available_templates,
)

_REQUIRED_TEMPLATES = ("layout.html", "page.html", "index.html")


def _display_path(path: Path, base: Path) -> str:
    """Return a friendly path display, relative when possible."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _check_optional_directory(
    path: Path,
    *,
    base: Path,
    label: str,
    missing_message: str,
) -> tuple[list[str], list[str]]:
    """Return warning/ok messages for an optional directory path."""
    display_path = _display_path(path, base)
    if path.is_dir():
        return [], [f"{label} directory: {display_path}"]
    if path.exists():
        return [f"{label} path is not a directory: {display_path}"], []
    return [], [missing_message]


def run_doctor(
    start_path: Path | None = None,
) -> tuple[list[str], list[str], list[str]]:
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
    except (TypeError, KeyError, ValueError) as e:
        errors.append(f"Invalid configuration: {e}")
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

    user_templates = get_user_templates_dir(vault_path)
    template_warnings, template_ok = _check_optional_directory(
        user_templates,
        base=start_path,
        label="User templates",
        missing_message="User templates directory not found (using bundled defaults).",
    )
    warnings.extend(template_warnings)
    ok.extend(template_ok)

    user_static = get_user_static_dir(vault_path)
    static_warnings, static_ok = _check_optional_directory(
        user_static,
        base=start_path,
        label="User static",
        missing_message="User static directory not found (using bundled defaults).",
    )
    warnings.extend(static_warnings)
    ok.extend(static_ok)

    return errors, warnings, ok
