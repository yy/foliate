"""Tests for foliate markdown utilities."""

import threading

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
        content = (
            "This is **bold** and *italic* text with some content here to make "
            "it long enough."
        )
        result = markdown_utils.extract_description(content)
        assert "**" not in result
        assert "bold" in result
        assert "italic" in result

    def test_strips_links(self):
        """Strips markdown links but keeps text."""
        content = (
            "Check out [this link](https://example.com) for more information "
            "about the topic."
        )
        result = markdown_utils.extract_description(content)
        assert "[" not in result
        assert "]" not in result
        assert "this link" in result
        assert "https://example.com" not in result

    def test_strips_images(self):
        """Removes image markdown completely."""
        content = (
            "Here is an image: ![alt text](image.png) and some more text to "
            "reach minimum."
        )
        result = markdown_utils.extract_description(content)
        assert "![" not in result
        assert "image.png" not in result

    def test_strips_code_blocks(self):
        """Removes code blocks."""
        content = (
            "Some text.\n\n```python\nprint('hello')\n```\n\nMore text here "
            "that is long enough to be a paragraph."
        )
        result = markdown_utils.extract_description(content)
        assert "```" not in result
        assert "print" not in result

    def test_prefers_wikilink_alias_text(self):
        """Uses the visible alias text for wikilinks in descriptions."""
        content = (
            "This paragraph references [[Private Note|a readable label]] and "
            "should keep only the visible label text in metadata."
        )
        result = markdown_utils.extract_description(content)
        assert "Private Note|" not in result
        assert "a readable label" in result

    def test_strips_wikilink_anchor_from_visible_description_text(self):
        """Bare wikilinks with heading anchors should use the visible page text."""
        content = (
            "This paragraph references [[Claude Code/Tips#tmux + Neovim Setup]] "
            "and should not leak the raw anchor into metadata descriptions."
        )
        result = markdown_utils.extract_description(content)
        assert "#tmux + Neovim Setup" not in result
        assert "Claude Code/Tips" in result

    def test_strips_headers(self):
        """Removes header markers."""
        content = (
            "# Header\n\nThis is a paragraph with enough content to be "
            "selected as description."
        )
        result = markdown_utils.extract_description(content)
        assert "#" not in result

    def test_truncates_long_content(self):
        """Truncates content longer than max_length."""
        content = "A" * 200
        result = markdown_utils.extract_description(content, max_length=100)
        assert len(result) <= 100
        assert result.endswith("...")

    def test_prefers_first_meaningful_paragraph(self):
        """Selects the first paragraph that has enough substance."""
        content = (
            "Intro.\n\n"
            "This second paragraph is long enough to be chosen as the description "
            "for this page and should be preferred."
        )
        result = markdown_utils.extract_description(content)
        assert result.startswith("This second paragraph is long enough")
        assert "Intro." not in result

    def test_strips_math_blocks(self):
        """Removes math blocks."""
        content = (
            "The equation $$E = mc^2$$ is famous and describes mass-energy "
            "equivalence clearly."
        )
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

    def test_strips_optional_markdown_image_title(self):
        """Ignores optional titles when extracting image destinations."""
        content = '![alt](image.png "Title")'
        assert markdown_utils.extract_first_image(content) == "image.png"

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

    def test_handles_malformed_frontmatter(self, tmp_path, capsys):
        """Returns empty dict and logs warning for malformed YAML."""
        md_file = tmp_path / "malformed.md"
        md_file.write_text(
            """---
title: Test
  bad_indent: this is invalid YAML indentation
  - also: mixed list and mapping
---

Content here.
"""
        )

        meta, content = markdown_utils.parse_markdown_file(md_file)

        assert meta == {}
        assert content == ""
        captured = capsys.readouterr()
        assert "YAML parsing error" in captured.err

    def test_handles_unclosed_frontmatter(self, tmp_path, capsys):
        """Returns empty dict for unclosed frontmatter delimiter."""
        md_file = tmp_path / "unclosed.md"
        md_file.write_text(
            """---
title: Test
public: true
No closing delimiter here.
"""
        )

        meta, content = markdown_utils.parse_markdown_file(md_file)

        # python-frontmatter is lenient, but content may be parsed unexpectedly
        # The key behavior is that it doesn't crash
        assert isinstance(meta, dict)
        assert isinstance(content, str)


class TestFixHomepageToWikiLinks:
    """Tests for fix_homepage_to_wiki_links() function."""

    def test_converts_wiki_links(self):
        """Converts wikilink anchors to wiki paths."""
        html = '<a class="wikilink" href="/Notes/Ideas/">Notes</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a class="wikilink" href="/wiki/Notes/Ideas/">Notes</a>'

    def test_preserves_wiki_links(self):
        """Doesn't double-prefix existing wiki links."""
        html = '<a class="wikilink" href="/wiki/Notes/">Notes</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a class="wikilink" href="/wiki/Notes/">Notes</a>'

    def test_preserves_regular_absolute_links(self):
        """Regular root links should not be rewritten to wiki paths."""
        html = '<a href="/about/">About</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html)
        assert result == '<a href="/about/">About</a>'

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

    def test_uses_custom_wiki_prefix(self):
        """Converts wikilinks using the configured wiki base URL."""
        html = '<a class="wikilink" href="/Notes/Ideas/">Notes</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(
            html, wiki_base_url="/pages/"
        )
        assert result == '<a class="wikilink" href="/pages/Notes/Ideas/">Notes</a>'

    def test_empty_wiki_prefix_leaves_wikilinks_at_root(self):
        """Root wiki mode should not add an extra prefix."""
        html = '<a class="wikilink" href="/Notes/Ideas/">Notes</a>'
        result = markdown_utils.fix_homepage_to_wiki_links(html, wiki_base_url="/")
        assert result == '<a class="wikilink" href="/Notes/Ideas/">Notes</a>'


class TestStripBackticksInWikilinkTargets:
    """Tests for backtick stripping in wikilink targets."""

    def test_backticks_in_anchor_stripped(self):
        """Backticks in heading anchors are stripped from target."""
        result = markdown_utils.render_markdown("[[Page#`code` heading|display text]]")
        assert 'href="/wiki/Page/#code heading"' in result
        assert "display text" in result

    def test_backticks_in_display_preserved(self):
        """Backticks in display text render as inline code."""
        result = markdown_utils.render_markdown("[[Page|check `config`]]")
        assert 'href="/wiki/Page/"' in result
        assert "<code>config</code>" in result

    def test_no_backticks_unchanged(self):
        """Wikilinks without backticks are not affected."""
        result = markdown_utils.render_markdown("[[Page#heading|display]]")
        assert 'href="/wiki/Page/#heading"' in result

    def test_backticks_in_target_without_display(self):
        """Backticks in target-only wikilink are stripped."""
        result = markdown_utils.render_markdown("[[Page#`tmux` setup]]")
        assert 'href="/wiki/Page/#tmux setup"' in result


class TestConfigureExtensions:
    """Tests for configure_extensions() and nl2br support."""

    def setup_method(self):
        """Reset extensions state before each test."""
        markdown_utils.configure_extensions(nl2br=False)

    def teardown_method(self):
        """Reset extensions state after each test."""
        markdown_utils.configure_extensions(nl2br=False)

    def test_nl2br_enabled_converts_newlines(self):
        """Single newlines become <br> when nl2br is enabled."""
        markdown_utils.configure_extensions(nl2br=True)
        result = markdown_utils.render_markdown("line one\nline two")
        assert "<br" in result

    def test_nl2br_disabled_collapses_newlines(self):
        """Single newlines collapse to spaces when nl2br is disabled."""
        markdown_utils.configure_extensions(nl2br=False)
        result = markdown_utils.render_markdown("line one\nline two")
        assert "<br" not in result
        assert "line one" in result
        assert "line two" in result

    def test_configure_clears_converter_cache(self):
        """Calling configure_extensions clears the converter cache."""
        # Build a cached converter
        markdown_utils.get_markdown_converter("/wiki/")
        cache = markdown_utils._get_thread_local_converter_cache()
        assert len(cache) > 0

        # Configure should clear it
        markdown_utils.configure_extensions(nl2br=True)
        cache = markdown_utils._get_thread_local_converter_cache()
        assert len(cache) == 0

    def test_get_extensions_includes_nl2br_when_enabled(self):
        """_get_extensions includes 'nl2br' at front when enabled."""
        markdown_utils.configure_extensions(nl2br=True)
        exts = markdown_utils._get_extensions()
        assert exts[0] == "nl2br"

    def test_get_extensions_excludes_nl2br_when_disabled(self):
        """_get_extensions does not include 'nl2br' when disabled."""
        markdown_utils.configure_extensions(nl2br=False)
        exts = markdown_utils._get_extensions()
        assert "nl2br" not in exts


class TestMarkdownConverterCaching:
    """Tests for Markdown converter reuse."""

    def test_get_markdown_converter_reuses_converter_per_base_url(self, monkeypatch):
        """Converters are cached per thread and base_url."""
        markdown_utils._MARKDOWN_CONVERTERS = threading.local()
        constructor_calls: list[dict[str, object]] = []

        class DummyMarkdown:
            def __init__(self, *, extensions, extension_configs):
                constructor_calls.append(
                    {
                        "extensions": extensions,
                        "extension_configs": extension_configs,
                    }
                )

            def reset(self):
                return self

            def convert(self, content):
                return content

        monkeypatch.setattr(markdown_utils.markdown, "Markdown", DummyMarkdown)

        wiki_converter = markdown_utils.get_markdown_converter("/wiki/")
        wiki_converter_again = markdown_utils.get_markdown_converter("/wiki/")
        home_converter = markdown_utils.get_markdown_converter("/")

        assert wiki_converter is wiki_converter_again
        assert home_converter is not wiki_converter
        assert len(constructor_calls) == 2
        assert (
            constructor_calls[0]["extension_configs"]["mdx_wikilink_plus"]["base_url"]
            == "/wiki/"
        )
        assert (
            constructor_calls[1]["extension_configs"]["mdx_wikilink_plus"]["base_url"]
            == "/"
        )

    def test_render_markdown_resets_cached_converter(self, monkeypatch):
        """render_markdown resets the cached converter before conversion."""
        markdown_utils._MARKDOWN_CONVERTERS = threading.local()

        class DummyMarkdown:
            def __init__(self):
                self.reset_calls = 0
                self.convert_calls = 0

            def reset(self):
                self.reset_calls += 1
                return self

            def convert(self, content):
                self.convert_calls += 1
                return content

        dummy = DummyMarkdown()
        monkeypatch.setattr(markdown_utils, "get_markdown_converter", lambda _: dummy)

        first = markdown_utils.render_markdown("first")
        second = markdown_utils.render_markdown("second")

        assert first == "first"
        assert second == "second"
        assert dummy.reset_calls == 2
        assert dummy.convert_calls == 2

    def test_render_markdown_skips_npx_only_katex_probe(
        self, monkeypatch, tmp_path
    ):
        """Plain markdown should not probe npx while configuring KaTeX."""
        import markdown_katex.wrapper as katex_wrapper

        fake_npx = tmp_path / "npx"
        fake_npx.write_text("", encoding="utf-8")

        original_parsed_options = katex_wrapper._PARSED_OPTIONS.copy()
        original_converters = markdown_utils._MARKDOWN_CONVERTERS

        try:
            katex_wrapper._PARSED_OPTIONS.clear()
            markdown_utils._MARKDOWN_CONVERTERS = threading.local()
            markdown_utils.configure_extensions(nl2br=False)

            monkeypatch.delattr(
                katex_wrapper, "_foliate_npx_probe_disabled", raising=False
            )
            monkeypatch.setattr(katex_wrapper, "_get_env_paths", lambda: [tmp_path])
            monkeypatch.setattr(
                katex_wrapper,
                "_get_local_bin_candidates",
                lambda: ["npx --no-install katex"],
            )

            def _fail_if_npx_is_probed(*args, **kwargs):
                raise AssertionError("npx probe should be skipped")

            monkeypatch.setattr(
                katex_wrapper.sp,
                "check_output",
                _fail_if_npx_is_probed,
            )

            result = markdown_utils.render_markdown("plain text")

            assert "<p>plain text</p>" in result
        finally:
            katex_wrapper._PARSED_OPTIONS.clear()
            katex_wrapper._PARSED_OPTIONS.update(original_parsed_options)
            markdown_utils._MARKDOWN_CONVERTERS = original_converters
            markdown_utils.configure_extensions(nl2br=False)
