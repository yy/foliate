"""Template management for foliate."""

from pathlib import Path

from jinja2 import BaseLoader, ChoiceLoader, FileSystemLoader, TemplateNotFound

from .resources import iter_package_files, read_package_text


class PackageLoader(BaseLoader):
    """Jinja2 loader that loads templates from a Python package."""

    def __init__(self, package: str):
        self.package = package

    def get_source(self, environment, template):
        source = read_package_text(self.package, template)
        if source is not None:
            # Return source, filename, and uptodate callable
            return source, f"{self.package}/{template}", lambda: True
        raise TemplateNotFound(template)

    def list_templates(self):
        return [name for name, _ in iter_package_files(self.package, suffix=".html")]


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


def get_template_path(name: str, vault_path: Path) -> Path | None:
    """Get the resolved path to a template.

    Checks user templates first, then bundled defaults.

    Args:
        name: Template filename (e.g., "page.html")
        vault_path: Path to the vault directory

    Returns:
        Path to the template file, or None if not found
    """
    from .resources import get_package_file_path

    # Check user templates first
    user_template = vault_path / ".foliate" / "templates" / name
    if user_template.exists():
        return user_template

    # Check bundled templates
    return get_package_file_path("foliate.defaults.templates", name)


def list_available_templates(vault_path: Path) -> dict[str, str]:
    """List all available templates and their sources.

    Args:
        vault_path: Path to the vault directory

    Returns:
        Dict mapping template names to their source ("user" or "bundled")
    """
    templates = {}

    # Check bundled templates first (will be overridden by user)
    for name, _ in iter_package_files("foliate.defaults.templates", suffix=".html"):
        templates[name] = "bundled"

    # Check user templates (override bundled)
    user_templates = vault_path / ".foliate" / "templates"
    if user_templates.exists():
        for template_file in user_templates.glob("*.html"):
            templates[template_file.name] = "user"

    return templates
