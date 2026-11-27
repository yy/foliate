"""Markdown extension for Obsidian highlights: ``==text==`` -> ``<mark>``.

The highlighted text may contain other inline Markdown, such as emphasis,
links, and wikilinks. The text must not start or end with whitespace, so
comparisons like ``a == b`` stay as written. Code spans and math are
processed first, so ``==`` inside them is untouched.
"""

from markdown import Extension
from markdown.inlinepatterns import SimpleTagInlineProcessor

_HIGHLIGHT_RE = r"(==)(?![\s=])(.+?)(?<![\s=])=="


class HighlightExtension(Extension):
    """Register the ``==text==`` inline pattern."""

    def extendMarkdown(self, md) -> None:
        # Just above emphasis (60), below code spans (190) and escapes (180).
        md.inlinePatterns.register(
            SimpleTagInlineProcessor(_HIGHLIGHT_RE, "mark"), "foliate_highlight", 65
        )


def makeExtension(**kwargs) -> HighlightExtension:  # noqa: N802
    """Entry point for python-markdown extension loading."""
    return HighlightExtension(**kwargs)
