"""Tests for the autolink markdown extension."""

from foliate.markdown_utils import render_markdown


def render(text: str) -> str:
    return render_markdown(text)


class TestAutolink:
    def test_modern_tld_is_linked(self):
        # .dev postdates bleach's TLD list; the mdx-linkify pipeline missed it
        html = render("- https://herdr.dev")
        assert (
            '<a href="https://herdr.dev" rel="nofollow">https://herdr.dev</a>' in html
        )

    def test_classic_tld_is_linked(self):
        html = render("See https://example.com for details")
        assert '<a href="https://example.com" rel="nofollow">' in html

    def test_http_scheme(self):
        html = render("http://localhost:8000/wiki/")
        assert '<a href="http://localhost:8000/wiki/" rel="nofollow">' in html

    def test_schemeless_text_not_linked(self):
        html = render("visit example.dev sometime")
        assert "<a" not in html

    def test_trailing_punctuation_excluded(self):
        html = render("Read https://example.dev/docs.")
        assert '<a href="https://example.dev/docs" rel="nofollow">' in html
        assert "docs.</a>" not in html

    def test_trailing_paren_excluded(self):
        html = render("(see https://example.dev)")
        assert '<a href="https://example.dev" rel="nofollow">' in html

    def test_balanced_paren_kept(self):
        url = "https://en.wikipedia.org/wiki/Foo_(bar)"
        html = render(f"see {url}")
        assert f'<a href="{url}" rel="nofollow">' in html

    def test_multiple_urls_in_one_paragraph(self):
        html = render("both https://a.dev and https://b.app here")
        assert '<a href="https://a.dev" rel="nofollow">' in html
        assert '<a href="https://b.app" rel="nofollow">' in html
        assert " and " in html
        assert " here" in html

    def test_url_in_inline_code_untouched(self):
        html = render("run `curl https://example.dev` now")
        assert "<a" not in html

    def test_url_in_fenced_code_block_untouched(self):
        html = render("```\nhttps://example.dev\n```")
        assert "<a" not in html

    def test_existing_markdown_link_untouched(self):
        html = render("[herdr.dev](https://herdr.dev)")
        assert html.count("<a") == 1
        assert ">herdr.dev</a>" in html

    def test_url_after_inline_element_is_linked(self):
        # URL lives in the tail of the <em> element
        html = render("*note* https://example.dev")
        assert '<a href="https://example.dev" rel="nofollow">' in html

    def test_url_in_list_and_heading(self):
        html = render("## Links\n\n- https://example.dev\n- plain item")
        assert '<a href="https://example.dev" rel="nofollow">' in html
