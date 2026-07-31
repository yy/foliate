"""Markdown extension allowing a list to start right after a paragraph.

Python-Markdown requires a blank line between a paragraph and a following
list; CommonMark does not. Obsidian (and most users) write

    Five mechanisms:
    - one
    - two

and expect a list. This preprocessor inserts the missing blank line so the
core list parser picks it up.

Follows CommonMark's paragraph-interruption rule: bullet items (``-``, ``*``,
``+``) and ordered items starting at ``1.`` may interrupt a paragraph; other
ordered numbers may not (they are more likely prose, e.g. "2019. was a good
year"). Lines inside an existing list (previous line is a list item or an
indented continuation) are left alone so tight lists stay tight.
"""

import re

from markdown import Extension
from markdown.preprocessors import Preprocessor

# A list item that may interrupt a paragraph: bullet, or ordered starting at 1.
_INTERRUPTING_ITEM = re.compile(r"^[ ]{0,3}(?:[-*+]|1\.)[ ]")

# Any list item marker (any indent, any number) — used to detect that the
# previous line is already part of a list.
_ANY_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+\.)[ ]")


class BreaklessListPreprocessor(Preprocessor):
    """Insert a blank line between a paragraph line and a following list."""

    def run(self, lines: list[str]) -> list[str]:
        new_lines: list[str] = []
        prev = ""
        for line in lines:
            if (
                _INTERRUPTING_ITEM.match(line)
                and prev.strip()
                and not prev.startswith((" ", "\t"))
                and not _ANY_ITEM.match(prev)
            ):
                new_lines.append("")
            new_lines.append(line)
            prev = line
        return new_lines


class BreaklessListExtension(Extension):
    """Markdown extension registering the breakless-list preprocessor."""

    def extendMarkdown(self, md) -> None:
        # Priority 9: after fenced code blocks (25) and HTML blocks (20) have
        # been stashed, so fence/HTML content is never touched.
        md.preprocessors.register(
            BreaklessListPreprocessor(md), "foliate_breakless_lists", 9
        )


def makeExtension(**kwargs) -> BreaklessListExtension:  # noqa: N802
    """Entry point for python-markdown extension loading."""
    return BreaklessListExtension(**kwargs)
