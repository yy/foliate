"""Tests for postprocess module."""

import tempfile
from pathlib import Path

from foliate.postprocess import (
    extract_wiki_path,
    postprocess_links,
    process_html_file,
    sanitize_wikilinks,
)


class TestExtractWikiPath:
    """Tests for extract_wiki_path function."""

    def test_extracts_simple_path(self):
        assert extract_wiki_path("/wiki/PageName/", "wiki") == "PageName"

    def test_extracts_nested_path(self):
        assert extract_wiki_path("/wiki/Folder/SubPage/", "wiki") == "Folder/SubPage"

    def test_returns_none_for_non_wiki_path(self):
        assert extract_wiki_path("/about/", "wiki") is None

    def test_returns_none_for_empty_href(self):
        assert extract_wiki_path("", "wiki") is None

    def test_returns_none_for_none_href(self):
        assert extract_wiki_path(None, "wiki") is None

    def test_handles_custom_wiki_prefix(self):
        assert extract_wiki_path("/docs/PageName/", "docs") == "PageName"

    def test_returns_none_for_root_wiki_path(self):
        assert extract_wiki_path("/wiki/", "wiki") is None


class TestSanitizeWikilinks:
    """Tests for sanitize_wikilinks function."""

    def test_removes_private_link(self):
        html = '<p><a href="/wiki/PrivatePage/" class="wikilink">Private</a></p>'
        public_pages = set()  # No public pages

        result, modified, count, _ = sanitize_wikilinks(html, public_pages)

        assert modified is True
        assert count == 1
        assert "PrivatePage" not in result
        assert "Private" in result  # Text preserved
        assert "<a" not in result  # Link removed

    def test_keeps_public_link(self):
        html = '<p><a href="/wiki/PublicPage/" class="wikilink">Public</a></p>'
        public_pages = {"PublicPage"}

        result, modified, count, _ = sanitize_wikilinks(html, public_pages)

        assert modified is False
        assert count == 0
        assert 'href="/wiki/PublicPage/"' in result
        assert "wikilink" in result

    def test_removes_multiple_private_links(self):
        html = """
        <p><a href="/wiki/Private1/" class="wikilink">Link1</a></p>
        <p><a href="/wiki/Private2/" class="wikilink">Link2</a></p>
        """
        public_pages = set()

        result, modified, count, _ = sanitize_wikilinks(html, public_pages)

        assert modified is True
        assert count == 2

    def test_mixed_public_and_private(self):
        html = """
        <p><a href="/wiki/Public/" class="wikilink">Public</a></p>
        <p><a href="/wiki/Private/" class="wikilink">Private</a></p>
        """
        public_pages = {"Public"}

        result, modified, count, _ = sanitize_wikilinks(html, public_pages)

        assert modified is True
        assert count == 1
        assert 'href="/wiki/Public/"' in result
        assert 'href="/wiki/Private/"' not in result

    def test_preserves_non_wikilinks(self):
        html = '<p><a href="https://example.com">External</a></p>'
        public_pages = set()

        result, modified, count, _ = sanitize_wikilinks(html, public_pages)

        assert modified is False
        assert '<a href="https://example.com">' in result

    def test_cleans_escaped_dollar_signs(self):
        html = "<p>Price is \\$100</p>"
        public_pages = set()

        result, modified, _, cleaned_dollars = sanitize_wikilinks(html, public_pages)

        assert modified is True
        assert cleaned_dollars is True
        assert "\\$" not in result
        assert "$" in result

    def test_preserves_dollar_in_code(self):
        html = "<code>echo \\$PATH</code>"
        public_pages = set()

        result, modified, _, cleaned_dollars = sanitize_wikilinks(html, public_pages)

        # Should not modify content in code tags
        assert "\\$" in result
        assert cleaned_dollars is False

    def test_preserves_inner_html_when_unwrapping(self):
        html = '<p><a href="/wiki/Private/" class="wikilink"><strong>Bold Private</strong></a></p>'
        public_pages = set()

        result, modified, count, _ = sanitize_wikilinks(html, public_pages)

        assert modified is True
        assert "<strong>Bold Private</strong>" in result
        assert "<a" not in result


class TestProcessHtmlFile:
    """Tests for process_html_file function."""

    def test_processes_file_with_private_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "test.html"
            html_file.write_text('<a href="/wiki/Private/" class="wikilink">Link</a>')

            public_pages = set()
            result = process_html_file(html_file, public_pages)

            assert result is True
            content = html_file.read_text()
            assert "<a" not in content

    def test_returns_false_when_no_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "test.html"
            html_file.write_text('<a href="/wiki/Public/" class="wikilink">Link</a>')

            public_pages = {"Public"}
            result = process_html_file(html_file, public_pages)

            assert result is False


class TestPostprocessLinks:
    """Tests for postprocess_links function."""

    def test_processes_build_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock config
            from foliate.config import Config

            config = Config()
            config.vault_path = Path(tmpdir)

            # Create build directory structure
            build_dir = Path(tmpdir) / ".foliate" / "build"
            wiki_dir = build_dir / "wiki" / "TestPage"
            wiki_dir.mkdir(parents=True)

            # Create test HTML file
            (wiki_dir / "index.html").write_text(
                '<a href="/wiki/Private/" class="wikilink">Private Link</a>'
            )

            public_pages = [{"path": "TestPage"}]

            result = postprocess_links(config, public_pages)

            assert result is True
            content = (wiki_dir / "index.html").read_text()
            assert "<a" not in content

    def test_returns_false_for_missing_build_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from foliate.config import Config

            config = Config()
            config.vault_path = Path(tmpdir) / "nonexistent"

            result = postprocess_links(config, [])

            assert result is False
