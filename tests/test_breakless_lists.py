"""Tests for the breakless-lists markdown extension (#18)."""

from foliate.markdown_utils import render_markdown


class TestBreaklessLists:
    def test_bullet_list_after_paragraph(self):
        """A bullet list directly after a paragraph renders as a list."""
        html = render_markdown("Five mechanisms:\n- **a** (67%)\n- **b** (12%)")
        assert "<ul>" in html
        assert html.count("<li>") == 2

    def test_ordered_list_after_paragraph(self):
        """An ordered list starting at 1. may interrupt a paragraph."""
        html = render_markdown("Steps:\n1. first\n2. second")
        assert "<ol>" in html
        assert html.count("<li>") == 2

    def test_non_one_ordered_number_does_not_interrupt(self):
        """A line like '2019. ...' stays part of the paragraph."""
        html = render_markdown("It was a good year\n2019. and so on")
        assert "<ol" not in html
        assert "<li>" not in html

    def test_fenced_code_untouched(self):
        """Dash lines inside fenced code blocks are not turned into lists."""
        html = render_markdown("code:\n```\ntext\n- not a list\n```")
        assert "<li>" not in html
        assert "- not a list" in html

    def test_tight_list_stays_tight(self):
        """Indented continuation lines don't make the list loose."""
        html = render_markdown("- a\n  cont\n- b")
        assert "<li><p>" not in html

    def test_blank_line_case_unchanged(self):
        """The already-correct form (blank line before list) still works."""
        html = render_markdown("Intro:\n\n- a\n- b")
        assert "<ul>" in html
        assert html.count("<li>") == 2

    def test_nested_list_unchanged(self):
        """Nested list items don't get a spurious blank line."""
        html = render_markdown("- a\n    - a1\n- b")
        assert html.count("<ul>") == 2
