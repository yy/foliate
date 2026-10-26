"""Tests for build-time Mermaid rendering with Pele."""

import shutil

import pytest

from foliate import mermaid
from foliate.markdown_utils import render_markdown_with_toc

FLOWCHART = "flowchart LR\n  A[Start] --> B[End]\n"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def render(content: str) -> str:
    return render_markdown_with_toc(content, source="Notes")[0]


def fence(source: str, lang: str = "mermaid", ticks: str = "```") -> str:
    return f"{ticks}{lang}\n{source}{ticks}\n"


@pytest.fixture
def warnings(monkeypatch):
    messages: list[str] = []
    monkeypatch.setattr(mermaid, "warning", messages.append)
    monkeypatch.setattr(mermaid, "_warned_unavailable", False)
    return messages


@pytest.fixture
def renderer(monkeypatch):
    """Replace Node with a fake; returns the list of source batches seen."""
    calls: list[list[str]] = []

    def fake(sources: list[str]) -> list[dict[str, str]]:
        calls.append(sources)
        return [
            {"error": "Parse error"} if "BAD" in s else {"svg": f'<svg id="d{i}"/>'}
            for i, s in enumerate(sources)
        ]

    monkeypatch.setattr(mermaid, "render_diagrams", fake)
    return calls


def test_mermaid_fence_becomes_inline_svg(renderer, warnings):
    html = render(f"Intro\n\n{fence(FLOWCHART)}\nAfter\n")

    assert renderer == [[FLOWCHART]]
    assert '<div class="diagram no-katex"><svg id="d0"/></div>' in html
    assert "<p>Intro</p>" in html and "<p>After</p>" in html
    assert "<pre" not in html
    assert warnings == []


def test_all_diagrams_on_a_page_render_in_one_call(renderer, warnings):
    html = render(fence(FLOWCHART) + "\nText\n\n" + fence("pie\n  A: 1\n"))

    assert len(renderer) == 1 and len(renderer[0]) == 2
    assert 'id="d0"' in html and 'id="d1"' in html


def test_pages_without_diagrams_skip_the_renderer(renderer):
    render("Plain text\n\n" + fence("x = 1\n", lang="python"))

    assert renderer == []


def test_mermaid_shown_inside_a_longer_fence_stays_code(renderer):
    html = render(fence(fence(FLOWCHART), lang="markdown", ticks="````"))

    assert renderer == []
    assert "```mermaid" in html and "<svg" not in html


def test_failed_diagram_stays_code_and_warns_with_page_name(renderer, warnings):
    html = render(fence("BAD\n") + "\n" + fence(FLOWCHART))

    assert "BAD" in html and "<pre" in html
    assert 'id="d1"' in html
    assert warnings == ["Notes: Mermaid diagram 1 left as code: Parse error"]


def test_missing_node_leaves_code_and_warns_once(monkeypatch, warnings):
    monkeypatch.setattr(mermaid.shutil, "which", lambda name: None)

    first = render(fence(FLOWCHART))
    render(fence(FLOWCHART))

    assert "<pre" in first and "<svg" not in first
    assert warnings == [
        "Mermaid diagrams left as code blocks: `node` not found on PATH"
    ]


@needs_node
def test_pele_renders_themeable_svg(warnings):
    html = render(fence('flowchart LR\n  A["costs $5 and $6"] --> B[End]\n'))

    assert 'class="pele pele-flowchart"' in html
    assert "var(--pele-fg" in html
    assert "costs $5 and $6" in html  # dollar math must not touch diagram text
    assert warnings == []


@needs_node
def test_pele_syntax_error_reports_parse_error(warnings):
    html = render(fence("flowchart LR\n  A -->\n"))

    assert "<pre" in html and "<svg" not in html
    assert len(warnings) == 1
    assert warnings[0].startswith("Notes: Mermaid diagram 1 left as code: Parse error")


@needs_node
def test_render_diagrams_handles_non_ascii():
    [result] = mermaid.render_diagrams(["flowchart LR\n  A[D⁻¹A × “α”] --> B\n"])

    assert "D⁻¹A × “α”" in result["svg"]
