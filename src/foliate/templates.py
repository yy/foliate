"""Template management for foliate."""

import importlib.resources
from pathlib import Path
from typing import Optional

from jinja2 import BaseLoader, ChoiceLoader, FileSystemLoader, TemplateNotFound


class PackageLoader(BaseLoader):
    """Jinja2 loader that loads templates from a Python package."""

    def __init__(self, package: str):
        self.package = package

    def get_source(self, environment, template):
        try:
            pkg = importlib.resources.files(self.package)
            template_file = pkg.joinpath(template)
            if template_file.is_file():
                source = template_file.read_text(encoding="utf-8")
                # Return source, filename, and uptodate callable
                return source, str(template_file), lambda: True
        except (TypeError, FileNotFoundError):
            pass
        raise TemplateNotFound(template)

    def list_templates(self):
        templates = []
        try:
            pkg = importlib.resources.files(self.package)
            for item in pkg.iterdir():
                if item.is_file() and item.name.endswith(".html"):
                    templates.append(item.name)
        except (TypeError, FileNotFoundError):
            pass
        return templates


def get_template_loader(vault_path: Path) -> ChoiceLoader:
    """Get a Jinja2 template loader with override support.

    Template resolution order:
    1. User templates in .foliate/templates/
    2. Bundled default templates

    Args:
        vault_path: Path to the vault directory

    Returns:
        ChoiceLoader that checks user templates first, then bundled defaults
    """
    loaders = []

    # Check for user template overrides
    user_templates = vault_path / ".foliate" / "templates"
    if user_templates.exists():
        loaders.append(FileSystemLoader(str(user_templates)))

    # Add bundled default templates
    loaders.append(PackageLoader("foliate.defaults.templates"))

    return ChoiceLoader(loaders)


def get_template_path(name: str, vault_path: Path) -> Optional[Path]:
    """Get the resolved path to a template.

    Checks user templates first, then bundled defaults.

    Args:
        name: Template filename (e.g., "page.html")
        vault_path: Path to the vault directory

    Returns:
        Path to the template file, or None if not found
    """
    # Check user templates first
    user_template = vault_path / ".foliate" / "templates" / name
    if user_template.exists():
        return user_template

    # Check bundled templates
    try:
        pkg = importlib.resources.files("foliate.defaults.templates")
        template_file = pkg.joinpath(name)
        if template_file.is_file():
            # For package resources, return a path-like representation
            # Note: This may not be a real filesystem path for zipped packages
            return Path(str(template_file))
    except (TypeError, FileNotFoundError):
        pass

    return None


def list_available_templates(vault_path: Path) -> dict[str, str]:
    """List all available templates and their sources.

    Args:
        vault_path: Path to the vault directory

    Returns:
        Dict mapping template names to their source ("user" or "bundled")
    """
    templates = {}

    # Check bundled templates first (will be overridden by user)
    try:
        pkg = importlib.resources.files("foliate.defaults.templates")
        for item in pkg.iterdir():
            if item.is_file() and item.name.endswith(".html"):
                templates[item.name] = "bundled"
    except (TypeError, FileNotFoundError):
        pass

    # Check user templates (override bundled)
    user_templates = vault_path / ".foliate" / "templates"
    if user_templates.exists():
        for template_file in user_templates.glob("*.html"):
            templates[template_file.name] = "user"

    return templates
