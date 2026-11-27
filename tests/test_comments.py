"""Tests for stripping Obsidian ``%%`` comments."""

import logging

from foliate import build
from foliate.comments import strip_comments
from foliate.config import Config


def _strip(source: str) -> str:
    text, unclosed = strip_comments(source)
    assert not unclosed
    return text


def test_inline_comment():
    assert _strip("Visible %%hidden%% text.\n") == "Visible  text.\n"


def test_two_inline_comments_on_one_line():
    assert _strip("a %%x%% b %%y%% c") == "a  b  c"


def test_block_comment_leaves_no_blank_lines():
    source = "- a\n%%\n- hidden\n%%\n- b\n"
    assert _strip(source) == "- a\n- b\n"


def test_comment_across_lines_inside_paragraph():
    assert _strip("start %%one\ntwo%% end\n") == "start \n end\n"


def test_text_without_comments_is_unchanged():
    source = "Rates rose 5% and 10%.\n"
    assert strip_comments(source) == (source, False)


def test_fenced_code_is_literal():
    source = "```mermaid\ngraph TD\n%% a Mermaid comment\nA --> B\n```\nafter %%x%%\n"
    assert _strip(source) == (
        "```mermaid\ngraph TD\n%% a Mermaid comment\nA --> B\n```\nafter \n"
    )


def test_tilde_fence_and_longer_closing_fence():
    source = "~~~\n%%kept%%\n~~~~\n%%gone%%\n"
    assert _strip(source) == "~~~\n%%kept%%\n~~~~\n"


def test_backtick_fence_ignores_tilde_close():
    source = "```\n~~~\n%%kept%%\n```\n"
    assert _strip(source) == source


def test_fence_inside_blockquote_is_literal():
    source = "> ```\n> %%kept%%\n> ```\n"
    assert _strip(source) == source


def test_inline_code_is_literal():
    assert _strip("Use `%%timeit` here %%not this%%.") == "Use `%%timeit` here ."


def test_double_backtick_code_span():
    assert _strip("``a ` %%b%%`` %%c%%") == "``a ` %%b%%`` "


def test_fence_inside_comment_is_hidden():
    source = "before\n%%\n```\ncode\n```\n%%\nafter\n"
    assert _strip(source) == "before\nafter\n"


def test_unclosed_comment_hides_rest_of_page():
    text, unclosed = strip_comments("Shown.\n\n%% draft\nmore draft\n")
    assert unclosed
    assert text == "Shown.\n\n"


def test_build_never_publishes_comment_text(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr("foliate.logging._logger", logging.getLogger(__name__))
    foliate_dir = tmp_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text("[build]\n", encoding="utf-8")
    (tmp_path / "note.md").write_text(
        "---\npublic: true\npublished: true\n---\n"
        "%%SECRETONE%%This page explains a comment-free summary sentence.\n\n"
        "%%\nSECRETTWO\n%%\n\nVisible paragraph.\n",
        encoding="utf-8",
    )
    (tmp_path / "draft.md").write_text(
        "---\npublic: true\n---\nShown.\n\n%% SECRETTHREE\n", encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING):
        build.build(config=Config.load(config_path))

    output = foliate_dir / "build"
    html = (output / "wiki" / "note" / "index.html").read_text(encoding="utf-8")
    assert "Visible paragraph." in html
    assert "This page explains a comment-free summary sentence." in html
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".json", ".xml", ".txt"}:
            text = path.read_text(encoding="utf-8")
            assert "SECRET" not in text, path
    assert "draft: unclosed %% comment" in caplog.text
