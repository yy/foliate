"""Tests for the floating table-of-contents option and .nojekyll output."""

from foliate import build
from foliate.config import Config
from foliate.page import Page


def _make_vault(tmp_path, build_extra=""):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    foliate_dir = vault_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text(
        f"""
[site]
name = "Test Site"
url = "https://test.com"

[build]
home_redirect = "test"
{build_extra}
"""
    )
    return vault_path, config_path


class TestPageToc:
    def test_toc_populated_from_headings(self):
        page = Page.from_markdown(
            "Note", {"title": "Note"}, "## First\n\ntext\n\n## Second\n\ntext"
        )
        assert "First" in page.toc
        assert "Second" in page.toc
        assert '<div class="toc">' in page.toc

    def test_toc_empty_without_headings(self):
        page = Page.from_markdown("Note", {"title": "Note"}, "just a paragraph")
        assert page.toc == ""


class TestFloatingTocConfig:
    def test_default_off(self, tmp_path):
        _, config_path = _make_vault(tmp_path)
        config = Config.load(config_path)
        assert config.build.floating_toc is False
        assert config.to_template_context()["floating_toc"] is False

    def test_enabled_via_toml(self, tmp_path):
        _, config_path = _make_vault(tmp_path, "floating_toc = true")
        config = Config.load(config_path)
        assert config.build.floating_toc is True


class TestFloatingTocBuild:
    def test_toc_rendered_when_enabled(self, tmp_path):
        vault_path, config_path = _make_vault(tmp_path, "floating_toc = true")
        (vault_path / "note.md").write_text(
            "---\ntitle: Note\npublic: true\n---\n## Alpha\n\ntext\n\n## Beta\n\ntext"
        )
        build.build(config=Config.load(config_path), force_rebuild=True)

        html = (
            vault_path / ".foliate" / "build" / "wiki" / "note" / "index.html"
        ).read_text()
        assert 'class="page-toc"' in html
        assert "#alpha" in html

    def test_toc_absent_when_disabled(self, tmp_path):
        vault_path, config_path = _make_vault(tmp_path)
        (vault_path / "note.md").write_text(
            "---\ntitle: Note\npublic: true\n---\n## Alpha\n\ntext"
        )
        build.build(config=Config.load(config_path), force_rebuild=True)

        html = (
            vault_path / ".foliate" / "build" / "wiki" / "note" / "index.html"
        ).read_text()
        assert 'class="page-toc"' not in html

    def test_toc_absent_without_headings(self, tmp_path):
        vault_path, config_path = _make_vault(tmp_path, "floating_toc = true")
        (vault_path / "note.md").write_text(
            "---\ntitle: Note\npublic: true\n---\nno headings here"
        )
        build.build(config=Config.load(config_path), force_rebuild=True)

        html = (
            vault_path / ".foliate" / "build" / "wiki" / "note" / "index.html"
        ).read_text()
        assert 'class="page-toc"' not in html


class TestNojekyll:
    def test_nojekyll_written_to_build_dir(self, tmp_path):
        vault_path, config_path = _make_vault(tmp_path)
        (vault_path / "note.md").write_text(
            "---\ntitle: Note\npublic: true\n---\ncontent"
        )
        build.build(config=Config.load(config_path), force_rebuild=True)

        assert (vault_path / ".foliate" / "build" / ".nojekyll").exists()
