"""Tests for foliate build system."""

from jinja2 import Environment

from foliate import build
from foliate.config import Config
from foliate.page import Page
from foliate.templates import get_template_loader


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
    """Tests for Page.from_markdown() function."""

    def test_creates_basic_page(self):
        """Creates page object with required fields."""
        meta = {"title": "Test Page", "public": True}
        content = "# Test\n\nSome content here."

        page = Page.from_markdown("test", meta, content, render_html=False)

        assert page.path == "test"
        assert page.title == "Test Page"
        assert page.body == content
        assert page.url == "/wiki/test/"

    def test_uses_path_as_default_title(self):
        """Uses path as title when not in meta."""
        meta = {"public": True}
        page = Page.from_markdown("my-page", meta, "content", render_html=False)

        assert page.title == "my-page"

    def test_extracts_description(self):
        """Auto-extracts description from content."""
        meta = {"public": True}
        content = (
            "This is a long enough paragraph that should be used as the "
            "description for the page."
        )

        page = Page.from_markdown("test", meta, content, render_html=False)

        assert page.description != ""
        assert "paragraph" in page.description

    def test_uses_meta_description(self):
        """Uses description from meta if provided."""
        meta = {"public": True, "description": "Custom description"}
        content = "Different content here."

        page = Page.from_markdown("test", meta, content, render_html=False)

        assert page.description == "Custom description"

    def test_extracts_image(self):
        """Auto-extracts image from content."""
        meta = {"public": True}
        content = "![alt](image.png)"

        page = Page.from_markdown("test", meta, content, render_html=False)

        assert page.image == "/assets/image.png"

    def test_uses_meta_image(self):
        """Uses image from meta if provided."""
        meta = {"public": True, "image": "/custom/image.png"}
        content = "![alt](other.png)"

        page = Page.from_markdown("test", meta, content, render_html=False)

        assert page.image == "/custom/image.png"

    def test_custom_base_url(self):
        """Respects custom base_url."""
        page = Page.from_markdown(
            "about", {}, "content", render_html=False, base_url="/"
        )

        assert page.url == "/about/"

    def test_includes_file_modification_time(self, tmp_path):
        """Includes file modification time when file_path provided."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")

        page = Page.from_markdown(
            "test", {}, "content", render_html=False, file_path=md_file
        )

        assert page.file_modified is not None
        assert page.file_mtime is not None


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
        result = build.build(config=config, force_rebuild=True)

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
        result = build.build(config=config, force_rebuild=True)

        assert result >= 1
        # Homepage content should be at root, not /wiki/
        assert (vault_path / ".foliate" / "build" / "about" / "index.html").exists()

    def test_search_index_uses_page_base_url_for_homepage_content(self, tmp_path):
        """search.json should use / URLs for _homepage content."""
        import json

        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://test.com"
"""
        )

        homepage_dir = vault_path / "_homepage"
        homepage_dir.mkdir()
        (homepage_dir / "about.md").write_text("---\npublic: true\n---\nAbout")
        (vault_path / "Home.md").write_text("---\npublic: true\n---\nWiki home")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        search_file = vault_path / ".foliate" / "build" / "wiki" / "search.json"
        entries = json.loads(search_file.read_text())
        by_path = {entry["path"]: entry for entry in entries}

        assert by_path["about"]["url"] == "/about/"
        assert by_path["Home"]["url"] == "/wiki/Home/"

    def test_sitemap_uses_page_base_url_for_homepage_content(self, tmp_path):
        """sitemap.txt should use / URLs for _homepage content."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test Site'\n")

        homepage_dir = vault_path / "_homepage"
        homepage_dir.mkdir()
        (homepage_dir / "about.md").write_text("---\npublic: true\n---\nAbout")
        (vault_path / "Home.md").write_text("---\npublic: true\n---\nWiki home")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        sitemap_file = vault_path / ".foliate" / "build" / "sitemap.txt"
        sitemap_lines = sitemap_file.read_text().splitlines()

        assert "/about/" in sitemap_lines
        assert "/wiki/Home/" in sitemap_lines

    def test_home_page_in_homepage_dir_does_not_render_under_wiki(self, tmp_path):
        """Home page from _homepage should only render at root location."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"

[build]
home_page = "about"
home_redirect = "about"
"""
        )

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
        build.build(config=config, force_rebuild=True)

        assert (vault_path / ".foliate" / "build" / "about" / "index.html").exists()
        assert not (
            vault_path / ".foliate" / "build" / "wiki" / "about" / "index.html"
        ).exists()

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
        result = build.build(config=config, force_rebuild=True)

        # No pages should be built (only the secret one exists and it's ignored)
        assert result == 0
        assert not (
            vault_path / ".foliate" / "build" / "wiki" / "secret" / "index.html"
        ).exists()

    def test_build_ignores_foliate_internal_markdown(self, tmp_path):
        """Markdown files under .foliate/ are never built as site pages."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test'")

        (vault_path / "public.md").write_text("---\npublic: true\n---\nPublic page")
        (foliate_dir / "notes.md").write_text("---\npublic: true\n---\nInternal note")

        config = Config.load(config_path)
        result = build.build(config=config, force_rebuild=True)

        assert result == 1
        assert (
            vault_path / ".foliate" / "build" / "wiki" / "public" / "index.html"
        ).exists()
        assert not (
            vault_path
            / ".foliate"
            / "build"
            / "wiki"
            / ".foliate"
            / "notes"
            / "index.html"
        ).exists()

    def test_wiki_root_redirect(self, tmp_path):
        """Wiki root (/wiki/) redirects to home page."""
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
home_page = "Home"
"""
        )

        # Create home page
        home_page = vault_path / "Home.md"
        home_page.write_text(
            """---
title: Home
public: true
---

Welcome home.
"""
        )

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        # Check wiki root redirect exists
        wiki_index = vault_path / ".foliate" / "build" / "wiki" / "index.html"
        assert wiki_index.exists()

        # Should redirect to /wiki/Home/
        content = wiki_index.read_text()
        assert "/wiki/Home/" in content

    def test_wiki_root_redirect_custom_home_page(self, tmp_path):
        """Wiki root redirect uses configured home page."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create .foliate config with custom home page
        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"

[build]
home_page = "Index"
"""
        )

        # Create the custom home page
        page = vault_path / "Index.md"
        page.write_text(
            """---
title: Index
public: true
---

This is the index.
"""
        )

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        wiki_index = vault_path / ".foliate" / "build" / "wiki" / "index.html"
        assert wiki_index.exists()

        content = wiki_index.read_text()
        assert "/wiki/Index/" in content

    def test_home_redirect_uses_actual_slugified_page_url(self, tmp_path):
        """Root redirect should follow built URLs instead of lowercasing raw config."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"

[build]
home_redirect = "My Page"
slugify_urls = true
"""
        )

        (vault_path / "My Page.md").write_text("---\npublic: true\n---\nHello")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        root_index = vault_path / ".foliate" / "build" / "index.html"
        assert "/wiki/My-Page/" in root_index.read_text()

    def test_wiki_root_redirect_uses_actual_page_url(self, tmp_path):
        """Wiki root redirect should point to the built page URL."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"

[build]
home_page = "about"
"""
        )

        homepage_dir = vault_path / "_homepage"
        homepage_dir.mkdir()
        (homepage_dir / "about.md").write_text("---\npublic: true\n---\nAbout")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        wiki_index = vault_path / ".foliate" / "build" / "wiki" / "index.html"
        assert "/about/" in wiki_index.read_text()

    def test_no_wiki_root_redirect_when_empty_prefix(self, tmp_path):
        """No wiki root redirect when wiki_prefix is empty."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        # Create .foliate config with empty wiki_prefix
        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"

[build]
wiki_prefix = ""
home_redirect = "Home"
"""
        )

        # Create a page
        page = vault_path / "Home.md"
        page.write_text(
            """---
title: Home
public: true
---

Home page.
"""
        )

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        # With empty wiki_prefix, there's no wiki directory to redirect
        wiki_dir = vault_path / ".foliate" / "build" / "wiki"
        assert not wiki_dir.exists()

    def test_single_page_build_does_not_regenerate_global_indexes(self, tmp_path):
        """single_page build should not overwrite search/sitemap with partial data."""
        import json

        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"
"""
        )

        (vault_path / "Alpha.md").write_text("---\npublic: true\n---\nAlpha")
        (vault_path / "Beta.md").write_text("---\npublic: true\n---\nBeta")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        search_file = vault_path / ".foliate" / "build" / "wiki" / "search.json"
        sitemap_file = vault_path / ".foliate" / "build" / "sitemap.txt"
        search_before = json.loads(search_file.read_text())
        sitemap_before = sitemap_file.read_text()

        build.build(config=config, force_rebuild=False, single_page="Alpha")

        search_after = json.loads(search_file.read_text())
        sitemap_after = sitemap_file.read_text()

        assert len(search_before) == 2
        assert len(search_after) == 2
        assert sitemap_before == sitemap_after


class TestStalePageRemoval:
    """Tests for stale page cleanup during incremental builds."""

    def _make_vault(self, tmp_path):
        """Create a minimal vault with config."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
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
        return vault_path, config_path

    def test_stale_html_removed_when_page_becomes_private(self, tmp_path):
        """When a page changes from public to private, its HTML is removed."""
        vault_path, config_path = self._make_vault(tmp_path)

        # Create a public page
        page = vault_path / "secret.md"
        page.write_text("---\ntitle: Secret\npublic: true\n---\nSecret content.")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        output = vault_path / ".foliate" / "build" / "wiki" / "secret" / "index.html"
        assert output.exists()

        # Make the page private and rebuild incrementally
        page.write_text("---\ntitle: Secret\npublic: false\n---\nSecret content.")
        config = Config.load(config_path)
        build.build(config=config, force_rebuild=False, incremental=True)

        assert not output.exists()

    def test_stale_html_removed_when_page_deleted(self, tmp_path):
        """When a source file is deleted, its HTML is removed."""
        vault_path, config_path = self._make_vault(tmp_path)

        page = vault_path / "temp.md"
        page.write_text("---\ntitle: Temp\npublic: true\n---\nTemp content.")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        output = vault_path / ".foliate" / "build" / "wiki" / "temp" / "index.html"
        assert output.exists()

        # Delete the source file and rebuild
        page.unlink()
        config = Config.load(config_path)
        build.build(config=config, force_rebuild=False, incremental=True)

        assert not output.exists()

    def test_stale_cleanup_removes_empty_directories(self, tmp_path):
        """Parent directories are cleaned up when they become empty."""
        vault_path, config_path = self._make_vault(tmp_path)

        subdir = vault_path / "Notes"
        subdir.mkdir()
        page = subdir / "draft.md"
        page.write_text("---\ntitle: Draft\npublic: true\n---\nDraft content.")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        output_dir = vault_path / ".foliate" / "build" / "wiki" / "Notes" / "draft"
        assert output_dir.exists()

        # Delete the source and rebuild
        page.unlink()
        config = Config.load(config_path)
        build.build(config=config, force_rebuild=False, incremental=True)

        # Both the page dir and the Notes dir under wiki should be gone
        assert not output_dir.exists()
        assert not (vault_path / ".foliate" / "build" / "wiki" / "Notes").exists()

    def test_no_stale_cleanup_on_force_rebuild(self, tmp_path):
        """Force rebuild wipes the build dir, so stale cleanup is not needed."""
        vault_path, config_path = self._make_vault(tmp_path)

        page = vault_path / "gone.md"
        page.write_text("---\ntitle: Gone\npublic: true\n---\nGone content.")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        output = vault_path / ".foliate" / "build" / "wiki" / "gone" / "index.html"
        assert output.exists()

        # Delete source and force rebuild — the build dir is wiped entirely
        page.unlink()
        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        assert not output.exists()

    def test_no_stale_cleanup_on_single_page_build(self, tmp_path):
        """Single-page build should not remove other pages."""
        vault_path, config_path = self._make_vault(tmp_path)

        page_a = vault_path / "alpha.md"
        page_a.write_text("---\ntitle: Alpha\npublic: true\n---\nAlpha")

        page_b = vault_path / "beta.md"
        page_b.write_text("---\ntitle: Beta\npublic: true\n---\nBeta")

        config = Config.load(config_path)
        build.build(config=config, force_rebuild=True)

        output_b = vault_path / ".foliate" / "build" / "wiki" / "beta" / "index.html"
        assert output_b.exists()

        # Delete beta's source, but do a single-page build of alpha only
        page_b.unlink()
        config = Config.load(config_path)
        build.build(
            config=config, force_rebuild=False, incremental=True, single_page="alpha"
        )

        # Beta's output should still be there (single_page build doesn't clean stale)
        assert output_b.exists()


class TestBuildStats:
    """Tests for build statistics reporting."""

    def test_process_markdown_files_counts_skipped_private_pages(self, tmp_path):
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test'")

        (vault_path / "public.md").write_text("---\npublic: true\n---\nPublic")
        (vault_path / "private.md").write_text("---\npublic: false\n---\nPrivate")

        config = Config.load(config_path)
        build_dir = config.get_build_dir()
        build_dir.mkdir(parents=True, exist_ok=True)
        env = Environment(loader=get_template_loader(vault_path))

        _, _, _, stats = build.process_markdown_files(
            vault_path=vault_path,
            build_dir=build_dir,
            env=env,
            config=config,
            build_cache={},
            force_rebuild=False,
            incremental=False,
        )

        assert stats["rebuilt_count"] == 1
        assert stats["skipped_count"] == 1
