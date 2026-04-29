"""Tests for template lookup helpers."""

from jinja2 import ChoiceLoader, FileSystemLoader

from foliate.templates import (
    DEFAULT_TEMPLATES_PACKAGE,
    PackageLoader,
    get_template_loader,
    get_template_path,
    get_user_templates_dir,
    list_available_templates,
)


def test_get_user_templates_dir_returns_standard_project_path(tmp_path):
    """The user template override path should have one shared definition."""
    assert get_user_templates_dir(tmp_path) == tmp_path / ".foliate" / "templates"


def test_template_loader_checks_user_templates_before_bundled_defaults(tmp_path):
    """User templates should keep taking precedence over bundled templates."""
    user_templates = get_user_templates_dir(tmp_path)
    user_templates.mkdir(parents=True)

    loader = get_template_loader(tmp_path)

    assert isinstance(loader, ChoiceLoader)
    assert isinstance(loader.loaders[0], FileSystemLoader)
    assert isinstance(loader.loaders[1], PackageLoader)
    assert loader.loaders[1].package == DEFAULT_TEMPLATES_PACKAGE


def test_get_template_path_prefers_user_template(tmp_path):
    """A user template override should resolve before the bundled default."""
    user_templates = get_user_templates_dir(tmp_path)
    user_templates.mkdir(parents=True)
    custom_page = user_templates / "page.html"
    custom_page.write_text("custom", encoding="utf-8")

    assert get_template_path("page.html", tmp_path) == custom_page


def test_list_available_templates_marks_user_overrides(tmp_path):
    """Template listings should still report user overrides distinctly."""
    user_templates = get_user_templates_dir(tmp_path)
    user_templates.mkdir(parents=True)
    (user_templates / "page.html").write_text("custom", encoding="utf-8")

    templates = list_available_templates(tmp_path)

    assert templates["layout.html"] == "bundled"
    assert templates["page.html"] == "user"
