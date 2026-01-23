"""Tests for foliate markdown utilities."""

from foliate import markdown_utils


class TestProcessAssetPaths:
    """Tests for process_asset_paths() function."""

    def test_converts_src_double_quotes(self):
        """Converts src="assets/ to src="/assets/."""
        html = '<img src="assets/image.png">'
        result = markdown_utils.process_asset_paths(html)
        assert result == '<img src="/assets/image.png">'

    def test_converts_src_single_quotes(self):
        """Converts src='assets/ to src='/assets/."""
        html = "<img src='assets/image.png'>"
        result = markdown_utils.process_asset_paths(html)
        assert result == "<img src='/assets/image.png'>"

    def test_converts_href_double_quotes(self):
        """Converts href="assets/ to href="/assets/."""
        html = '<a href="assets/doc.pdf">Download</a>'
        result = markdown_utils.process_asset_paths(html)
        assert result == '<a href="/assets/doc.pdf">Download</a>'

    def test_converts_href_single_quotes(self):
        """Converts href='assets/ to href='/assets/."""
        html = "<a href='assets/doc.pdf'>Download</a>"
        result = markdown_utils.process_asset_paths(html)
        assert result == "<a href='/assets/doc.pdf'>Download</a>"

    def test_leaves_absolute_paths_unchanged(self):
        """Doesn't modify already-absolute asset paths."""
        html = '<img src="/assets/image.png">'
        result = markdown_utils.process_asset_paths(html)
        assert result == '<img src="/assets/image.png">'

    def test_leaves_external_urls_unchanged(self):
        """Doesn't modify external URLs."""
        html = '<img src="https://example.com/image.png">'
        result = markdown_utils.process_asset_paths(html)
        assert result == '<img src="https://example.com/image.png">'


class TestExtractDescription:
    """Tests for extract_description() function."""

    def test_empty_content(self):
        """Returns empty string for empty content."""
        assert markdown_utils.extract_description("") == ""

    def test_strips_markdown_formatting(self):
        """Strips bold, italic, and other markdown formatting."""
        content = "This is **bold** and *italic* text with some content here to make it long enough."
        result = markdown_utils.extract_description(content)
        assert "**" not in result
        assert "bold" in result
        assert "italic" in result

    def test_strips_links(self):
        """Strips markdown links but keeps text."""
        content = "Check out [this link](https://example.com) for more information about the topic."
        result = markdown_utils.extract_description(content)
        assert "[" not in result
        assert "]" not in result
        assert "this link" in result
        assert "https://example.com" not in result

    def test_strips_images(self):
        """Removes image markdown completely."""
        content = "Here is an image: ![alt text](image.png) and some more text to reach minimum."
        result = markdown_utils.extract_description(content)
        assert "![" not in result
        assert "image.png" not in result

    def test_strips_code_blocks(self):
        """Removes code blocks."""
        content = "Some text.\n\n```python\nprint('hello')\n```\n\nMore text here that is long enough to be a paragraph."
        result = markdown_utils.extract_description(content)
        assert "```" not in result
        assert "print" not in result

    def test_strips_headers(self):
        """Removes header markers."""
        content = "# Header\n\nThis is a paragraph with enough content to be selected as description."
        result = markdown_utils.extract_description(content)
        assert "#" not in result

    def test_truncates_long_content(self):
        """Truncates content longer than max_length."""
        content = "A" * 200
        result = markdown_utils.extract_description(content, max_length=100)
        assert len(result) <= 100
        assert result.endswith("...")

    def test_strips_math_blocks(self):
        """Removes math blocks."""
        content = "The equation $$E = mc^2$$ is famous and describes mass-energy equivalence clearly."
        result = markdown_utils.extract_description(content)
        assert "$$" not in result
        assert "E = mc^2" not in result


class TestExtractFirstImage:
    """Tests for extract_first_image() function."""

    def test_empty_content(self):
        """Returns None for empty content."""
        assert markdown_utils.extract_first_image("") is None
        assert markdown_utils.extract_first_image(None) is None

    def test_finds_markdown_image(self):
        """Finds markdown-style images."""
        content = "Some text ![alt](image.png) more text"
        assert markdown_utils.extract_first_image(content) == "image.png"

    def test_finds_html_image_double_quotes(self):
        """Finds HTML img tags with double quotes."""
        content = 'Some text <img src="image.png"> more text'
        assert markdown_utils.extract_first_image(content) == "image.png"

    def test_finds_html_image_single_quotes(self):
        """Finds HTML img tags with single quotes."""
        content = "Some text <img src='image.png'> more text"
        assert markdown_utils.extract_first_image(content) == "image.png"

    def test_returns_first_image(self):
        """Returns the first image when multiple exist."""
        content = "![first](first.png) and ![second](second.png)"
        assert markdown_utils.extract_first_image(content) == "first.png"

    def test_no_image_found(self):
        """Returns None when no image found."""
        content = "Just some text without any images"
        assert markdown_utils.extract_first_image(content) is None


class TestParseMarkdownFile:
    """Tests for parse_markdown_file() function."""

    def test_parses_frontmatter(self, tmp_path):
        """Correctly parses YAML frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text(
            """---
title: Test Page
public: true
tags:
  - test
  - example
---

# Content

This is the content.
"""
        )

        meta, content = markdown_utils.parse_markdown_file(md_file)

        assert meta["title"] == "Test Page"
        assert meta["public"] is True
        assert meta["tags"] == ["test", "example"]
        assert "# Content" in content
        assert "This is the content." in content

    def test_handles_no_frontmatter(self, tmp_path):
        """Handles files without frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Just Content\n\nNo frontmatter here.")

        meta, content = markdown_utils.parse_markdown_file(md_file)

        assert meta == {}
        assert "# Just Content" in content


class TestFixHomepageToWikiLinks:
    """Tests for fix_homepage_to_wiki_links() function."""

    def test_converts_wiki_links(self):
        """Converts internal links to wiki paths."""
        html = '<a href="/Notes/Ideas/">Notes</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a href="/wiki/Notes/Ideas/">Notes</a>'

    def test_preserves_wiki_links(self):
        """Doesn't double-prefix existing wiki links."""
        html = '<a href="/wiki/Notes/">Notes</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a href="/wiki/Notes/">Notes</a>'

    def test_preserves_asset_links(self):
        """Preserves asset links."""
        html = '<a href="/assets/doc.pdf">Download</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a href="/assets/doc.pdf">Download</a>'

    def test_preserves_external_links(self):
        """Preserves links starting with http/https."""
        html = '<a href="https://example.com">External</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a href="https://example.com">External</a>'

    def test_preserves_anchor_links(self):
        """Preserves anchor links."""
        html = '<a href="#section">Jump</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a href="#section">Jump</a>'
