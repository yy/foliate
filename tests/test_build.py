"""Tests for foliate build system."""

from foliate import build
from foliate.config import Config


class TestGetContentInfo:
    """Tests for get_content_info() helper."""

    def test_homepage_content(self):
        """Correctly identifies and strips homepage prefix."""
        page_path, base_url, is_homepage = build.get_content_info(
            "_homepage/about", "_homepage"
        )

        assert page_path == "about"
        assert base_url == "/"
        assert is_homepage is True

    def test_wiki_content(self):
        """Correctly identifies wiki content."""
        page_path, base_url, is_homepage = build.get_content_info(
            "Notes/Ideas", "_homepage"
        )

        assert page_path == "Notes/Ideas"
        assert base_url == "/wiki/"
        assert is_homepage is False

    def test_nested_homepage_content(self):
        """Handles nested homepage content paths."""
        page_path, base_url, is_homepage = build.get_content_info(
            "_homepage/research/projects", "_homepage"
        )

        assert page_path == "research/projects"
        assert base_url == "/"
        assert is_homepage is True

    def test_custom_wiki_prefix(self):
        """Respects custom wiki base URL."""
        page_path, base_url, is_homepage = build.get_content_info(
            "Notes/Ideas", "_homepage", wiki_base_url="/pages/"
        )

        assert page_path == "Notes/Ideas"
        assert base_url == "/pages/"
        assert is_homepage is False


class TestCreatePageObject:
    """Tests for create_page_object() function."""

    def test_creates_basic_page(self):
        """Creates page object with required fields."""
        meta = {"title": "Test Page", "public": True}
        content = "# Test\n\nSome content here."

        page = build.create_page_object("test", meta, content, render_html=False)

        assert page["path"] == "test"
        assert page["title"] == "Test Page"
        assert page["body"] == content
        assert page["url"] == "/wiki/test/"

    def test_uses_path_as_default_title(self):
        """Uses path as title when not in meta."""
        meta = {"public": True}
        page = build.create_page_object("my-page", meta, "content", render_html=False)

        assert page["title"] == "my-page"

    def test_extracts_description(self):
        """Auto-extracts description from content."""
        meta = {"public": True}
        content = "This is a long enough paragraph that should be used as the description for the page."

        page = build.create_page_object("test", meta, content, render_html=False)

        assert page["description"] != ""
        assert "paragraph" in page["description"]

    def test_uses_meta_description(self):
        """Uses description from meta if provided."""
        meta = {"public": True, "description": "Custom description"}
        content = "Different content here."

        page = build.create_page_object("test", meta, content, render_html=False)

        assert page["description"] == "Custom description"

    def test_extracts_image(self):
        """Auto-extracts image from content."""
        meta = {"public": True}
        content = "![alt](image.png)"

        page = build.create_page_object("test", meta, content, render_html=False)

        assert page["image"] == "/assets/image.png"

    def test_uses_meta_image(self):
        """Uses image from meta if provided."""
        meta = {"public": True, "image": "/custom/image.png"}
        content = "![alt](other.png)"

        page = build.create_page_object("test", meta, content, render_html=False)

        assert page["image"] == "/custom/image.png"

    def test_custom_base_url(self):
        """Respects custom base_url."""
        page = build.create_page_object(
            "about", {}, "content", render_html=False, base_url="/"
        )

        assert page["url"] == "/about/"

    def test_includes_file_modification_time(self, tmp_path):
        """Includes file modification time when file_path provided."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")

        page = build.create_page_object(
            "test", {}, "content", render_html=False, file_path=md_file
        )

        assert "file_modified" in page
        assert "file_mtime" in page


class TestIsPathIgnored:
    """Tests for is_path_ignored() helper function."""

    def test_ignores_top_level_folder(self, tmp_path):
        """Files in top-level ignored folder are ignored."""
        ignored_dir = tmp_path / "_private"
        ignored_dir.mkdir()
        file_path = ignored_dir / "secret.md"
        file_path.touch()

        assert build.is_path_ignored(file_path, tmp_path, ["_private"]) is True

    def test_ignores_nested_folder(self, tmp_path):
        """Files in nested ignored folder are ignored."""
        nested_dir = tmp_path / "docs" / "_private"
        nested_dir.mkdir(parents=True)
        file_path = nested_dir / "secret.md"
        file_path.touch()

        assert build.is_path_ignored(file_path, tmp_path, ["_private"]) is True

    def test_does_not_ignore_regular_folder(self, tmp_path):
        """Files in regular folders are not ignored."""
        regular_dir = tmp_path / "docs" / "public"
        regular_dir.mkdir(parents=True)
        file_path = regular_dir / "page.md"
        file_path.touch()

        assert build.is_path_ignored(file_path, tmp_path, ["_private"]) is False

    def test_multiple_ignored_folders(self, tmp_path):
        """Supports multiple ignored folder names."""
        private_dir = tmp_path / "_private"
        private_dir.mkdir()
        private_file = private_dir / "secret.md"
        private_file.touch()

        drafts_dir = tmp_path / "drafts"
        drafts_dir.mkdir()
        draft_file = drafts_dir / "wip.md"
        draft_file.touch()

        ignored_folders = ["_private", "drafts"]
        assert build.is_path_ignored(private_file, tmp_path, ignored_folders) is True
        assert build.is_path_ignored(draft_file, tmp_path, ignored_folders) is True

    def test_empty_ignored_list(self, tmp_path):
        """Empty ignored list ignores nothing."""
        ignored_dir = tmp_path / "_private"
        ignored_dir.mkdir()
        file_path = ignored_dir / "secret.md"
        file_path.touch()

        assert build.is_path_ignored(file_path, tmp_path, []) is False

    def test_partial_name_match_not_ignored(self, tmp_path):
        """Folder with partial name match is NOT ignored."""
        partial_dir = tmp_path / "_private_stuff"
        partial_dir.mkdir()
        file_path = partial_dir / "page.md"
        file_path.touch()

        assert build.is_path_ignored(file_path, tmp_path, ["_private"]) is False


class TestBuildIntegration:
    """Integration tests for the build process."""

    def test_build_single_page(self, tmp_path):
        """Can build a single page."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create .foliate config
        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://test.com"

[build]
home_redirect = "test"
"""
        )

        # Create a simple page
        page = vault_path / "test.md"
        page.write_text(
            """---
title: Test Page
public: true
---

# Hello World

This is a test page.
"""
        )

        config = Config.load(config_path)
        result = build.build(config=config, force_rebuild=True, verbose=False)

        assert result >= 1
        assert (
            vault_path / ".foliate" / "build" / "wiki" / "test" / "index.html"
        ).exists()

    def test_build_homepage_content(self, tmp_path):
        """Homepage content is built at root."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create .foliate config
        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"

[build]
home_redirect = "about"
"""
        )

        # Create homepage content
        homepage_dir = vault_path / "_homepage"
        homepage_dir.mkdir()
        about_page = homepage_dir / "about.md"
        about_page.write_text(
            """---
title: About
public: true
---

About page content.
"""
        )

        config = Config.load(config_path)
        result = build.build(config=config, force_rebuild=True, verbose=False)

        assert result >= 1
        # Homepage content should be at root, not /wiki/
        assert (vault_path / ".foliate" / "build" / "about" / "index.html").exists()

    def test_build_ignores_private_folder(self, tmp_path):
        """Files in _private are not built."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create .foliate config
        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test'")

        # Create a private page
        private_dir = vault_path / "_private"
        private_dir.mkdir()
        secret_page = private_dir / "secret.md"
        secret_page.write_text(
            """---
title: Secret
public: true
---

This should not be built.
"""
        )

        config = Config.load(config_path)
        result = build.build(config=config, force_rebuild=True, verbose=False)

        # No pages should be built (only the secret one exists and it's ignored)
        assert result == 0
        assert not (
            vault_path / ".foliate" / "build" / "wiki" / "secret" / "index.html"
        ).exists()
