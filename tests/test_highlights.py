"""Tests for Obsidian highlights (``==text==``)."""

from bs4 import BeautifulSoup

from foliate.markdown_utils import extract_description, render_markdown


def _soup(source: str) -> BeautifulSoup:
    return BeautifulSoup(render_markdown(source), "html.parser")


def test_highlight_renders_mark():
    soup = _soup("A ==key point== here.")
    assert soup.mark.get_text() == "key point"
    assert soup.p.get_text() == "A key point here."


def test_highlight_keeps_inline_markdown():
    soup = _soup("==see **this** and [[Other Page]]==")
    assert soup.mark.strong.get_text() == "this"
    assert soup.mark.a["class"] == ["wikilink"]


def test_spaced_equals_are_not_highlights():
    soup = _soup("If a == b and b == c, then a == c.")
    assert soup.mark is None
    assert soup.p.get_text() == "If a == b and b == c, then a == c."


def test_code_and_math_are_untouched():
    soup = _soup("`x ==y== z` and $a ==b== c$")
    assert soup.mark is None
    assert soup.code.get_text() == "x ==y== z"


def test_setext_heading_is_not_a_highlight():
    soup = _soup("Title\n=====\n\nBody.")
    assert soup.h1.get_text().startswith("Title")
    assert soup.mark is None


def test_description_drops_highlight_markers():
    content = "This sentence has a ==highlighted phrase== inside it for the summary."
    assert extract_description(content) == (
        "This sentence has a highlighted phrase inside it for the summary."
    )
