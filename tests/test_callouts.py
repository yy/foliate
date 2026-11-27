"""Tests for Obsidian callouts (``> [!type]`` blockquotes)."""

import logging

import pytest
from bs4 import BeautifulSoup

from foliate import build
from foliate.config import Config
from foliate.markdown_utils import extract_description, render_markdown


def _callout(source: str):
    soup = BeautifulSoup(render_markdown(source), "html.parser")
    callout = soup.find(class_="callout")
    assert callout is not None
    return callout


def test_minus_folds_closed():
    callout = _callout("> [!note]- Derivation\n> Step one.")
    assert callout.name == "details"
    assert callout["class"] == ["callout", "callout-note"]
    assert not callout.has_attr("open")
    summary = callout.find("summary", recursive=False)
    assert summary.get_text() == "Derivation"
    assert callout.select_one(".callout-content > p").get_text() == "Step one."


def test_plus_folds_open():
    callout = _callout("> [!tip]+ Shown\n> Body.")
    assert callout.name == "details"
    assert callout.has_attr("open")
    assert callout.summary.get_text() == "Shown"


def test_no_suffix_is_static_box():
    callout = _callout("> [!warning] Heads up\n> Body.")
    assert callout.name == "div"
    assert callout["class"] == ["callout", "callout-warning"]
    assert callout.select_one(".callout-title").get_text() == "Heads up"
    assert callout.find("summary") is None


@pytest.mark.parametrize(
    ("source", "title"),
    [("> [!note]\n> x", "Note"), ("> [!QUESTION]-\n> x", "Question")],
)
def test_missing_title_uses_capitalized_type(source, title):
    callout = _callout(source)
    assert callout.select_one(".callout-title").get_text() == title


def test_type_is_case_insensitive():
    assert _callout("> [!Warning]- T\n> x")["class"] == ["callout", "callout-warning"]


def test_header_only_callout_has_no_content():
    callout = _callout("> [!info] Just a title")
    assert callout.select_one(".callout-content") is None


def test_plain_blockquote_unchanged():
    html = render_markdown("> An ordinary quote\n> [!note] not a header")
    assert html == (
        "<blockquote>\n<p>An ordinary quote\n[!note] not a header</p>\n</blockquote>"
    )


def test_blank_line_ends_callout():
    soup = BeautifulSoup(
        render_markdown("> [!note]- A\n> in\n\n> after"), "html.parser"
    )
    assert soup.details.get_text().strip().endswith("in")
    assert soup.blockquote.get_text().strip() == "after"


def test_callout_may_interrupt_paragraph():
    soup = BeautifulSoup(render_markdown("Before\n> [!info] T\n> x"), "html.parser")
    assert soup.p.get_text() == "Before"
    assert soup.find(class_="callout-info") is not None


def test_body_renders_full_markdown():
    callout = _callout(
        "> [!note]- Derivation **of** $x$\n"
        "> Steps:\n"
        "> - see [[Other Page]]\n"
        "> - then $a_i^2$\n"
        ">\n"
        "> $$\n"
        "> a > b_{i}\n"
        "> $$"
    )
    assert callout.summary.strong.get_text() == "of"
    assert "$x$" in callout.summary.get_text()
    items = callout.select(".callout-content > ul > li")
    assert [li.get_text() for li in items] == ["see Other Page", "then $a_i^2$"]
    assert items[0].a["class"] == ["wikilink"]
    assert "$$\na > b_{i}\n$$" in callout.get_text()
    assert "FOLIATEMATHPLACEHOLDER" not in str(callout)


def test_nested_callouts():
    outer = _callout("> [!note]- Outer\n> text\n> > [!example]+ Inner\n> > deep")
    inner = outer.select_one(".callout-content > details.callout-example")
    assert inner is not None
    assert inner.has_attr("open")
    assert inner.select_one(".callout-content").get_text().strip() == "deep"


def test_description_drops_callout_marker():
    content = "> [!note]- Derivation of the block model likelihood, step by step."
    assert extract_description(content) == (
        "Derivation of the block model likelihood, step by step."
    )


def test_build_links_callout_stylesheet(tmp_path, monkeypatch):
    monkeypatch.setattr("foliate.logging._logger", logging.getLogger(__name__))
    foliate_dir = tmp_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text("[build]\n", encoding="utf-8")
    (tmp_path / "note.md").write_text(
        "---\npublic: true\n---\n> [!note]- Derivation\n> Step.\n", encoding="utf-8"
    )
    build.build(config=Config.load(config_path))

    output = foliate_dir / "build"
    html = (output / "wiki" / "note" / "index.html").read_text(encoding="utf-8")
    assert 'href="/static/callouts.css"' in html
    # Load before main.css so a site stylesheet can override callout colors.
    assert html.index("/static/callouts.css") < html.index("/static/main.css")
    assert '<details class="callout callout-note">' in html
    assert (output / "static" / "callouts.css").is_file()
