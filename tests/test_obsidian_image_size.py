"""Tests for Obsidian image size markdown extension."""

import markdown

from foliate.obsidian_image_size import ObsidianImageSizeExtension


def render_markdown(text):
    """Helper to render markdown with the obsidian image size extension."""
    md = markdown.Markdown(extensions=[ObsidianImageSizeExtension()])
    return md.convert(text)


class TestObsidianImageSize:
    """Tests for ObsidianImageSizeExtension."""

    def test_converts_image_with_width_only(self):
        """Converts ![|width](url) syntax."""
        text = "![|300](image.png)"
        result = render_markdown(text)
        assert '<img src="image.png" alt="" width="300">' in result

    def test_converts_image_with_alt_and_width(self):
        """Converts ![alt|width](url) syntax."""
        text = "![My image|500](photo.jpg)"
        result = render_markdown(text)
        assert '<img src="photo.jpg" alt="My image" width="500">' in result

    def test_preserves_regular_images(self):
        """Regular markdown images without size are unchanged."""
        text = "![alt text](image.png)"
        result = render_markdown(text)
        assert "<img" in result
        assert 'alt="alt text"' in result
        assert "width=" not in result

    def test_handles_multiple_images_per_line(self):
        """Converts multiple Obsidian images on the same line."""
        text = "![|100](a.png) and ![|200](b.png)"
        result = render_markdown(text)
        assert '<img src="a.png" alt="" width="100">' in result
        assert '<img src="b.png" alt="" width="200">' in result

    def test_escapes_html_in_alt_text(self):
        """Escapes HTML special characters in alt text."""
        text = '![<script>alert("xss")</script>|300](image.png)'
        result = render_markdown(text)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escapes_html_in_url(self):
        """Escapes HTML special characters in URL."""
        text = '![alt|300](image.png" onload="alert(1))'
        result = render_markdown(text)
        assert 'onload="alert' not in result
        assert "&quot;" in result or "&#" in result

    def test_handles_url_with_spaces(self):
        """Handles URLs that might have encoded spaces."""
        text = "![|300](my%20image.png)"
        result = render_markdown(text)
        assert '<img src="my%20image.png" alt="" width="300">' in result

    def test_inline_with_text(self):
        """Works when image is inline with text."""
        text = "Here is an image ![|200](pic.png) in text."
        result = render_markdown(text)
        assert '<img src="pic.png" alt="" width="200">' in result
        assert "Here is an image" in result
        assert "in text." in result

    def test_width_must_be_digits(self):
        """Only numeric widths are converted."""
        text = "![|abc](image.png)"
        result = render_markdown(text)
        # Should not be converted since width is not numeric
        assert "width=" not in result

    def test_empty_alt_text_stripped(self):
        """Empty alt text with spaces is stripped."""
        text = "![   |300](image.png)"
        result = render_markdown(text)
        assert 'alt=""' in result
