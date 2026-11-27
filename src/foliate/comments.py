"""Strip Obsidian comments (``%%hidden%%``) from page Markdown.

Obsidian hides ``%%…%%`` in reading view, inline or across lines. Foliate
strips them from the source before rendering, so the text never reaches the
HTML, page descriptions, the feed, or the search index. As in Obsidian,
``%%`` inside fenced code blocks (including Mermaid, which uses ``%%`` for its
own comments) and inline code spans is literal, and an unclosed ``%%`` hides
the rest of the page.
"""

import re

# A fence opener or closer, possibly inside blockquote markers.
_FENCE_RE = re.compile(r"^(?:[ \t]*>)*[ \t]{0,3}(`{3,}|~{3,})(.*)$")


def _fence(line: str) -> tuple[str, str] | None:
    """Return (fence, info string) when the line is a code fence."""
    match = _FENCE_RE.match(line.rstrip("\r\n"))
    if match is None:
        return None
    fence, info = match.groups()
    if fence[0] == "`" and "`" in info:
        return None  # CommonMark: a backtick fence's info string has no backticks
    return fence, info


def _strip_line(line: str, in_comment: bool) -> tuple[str, bool, bool]:
    """Strip comment text from one line, skipping inline code spans.

    Returns (kept text, still in a comment, whether the line had comment text).
    """
    kept: list[str] = []
    had_comment = in_comment
    i, n = 0, len(line)
    while i < n:
        if in_comment:
            close = line.find("%%", i)
            if close == -1:
                break
            i, in_comment = close + 2, False
            continue
        if line[i] == "`":
            rest = line[i:]
            run = len(rest) - len(rest.lstrip("`"))
            ticks = "`" * run
            close = line.find(ticks, i + run)
            # A closing run must be exactly as long as the opening run.
            while close != -1 and line[close + run : close + run + 1] == "`":
                close = line.find(ticks, close + run + 1)
            end = close + run if close != -1 else i + run
            kept.append(line[i:end])
            i = end
            continue
        if line.startswith("%%", i):
            i, in_comment, had_comment = i + 2, True, True
            continue
        kept.append(line[i])
        i += 1
    text = "".join(kept)
    if in_comment and line.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text, in_comment, had_comment


def strip_comments(markdown_content: str) -> tuple[str, bool]:
    """Remove Obsidian ``%%`` comments from Markdown.

    Returns the stripped Markdown and whether a comment was left unclosed.
    A line that held only comment text is dropped, so a hidden block between
    list items or paragraphs leaves no extra blank lines behind.
    """
    if "%%" not in markdown_content:
        return markdown_content, False

    out: list[str] = []
    in_comment = False
    open_fence: str | None = None
    for line in markdown_content.splitlines(keepends=True):
        if open_fence is not None:
            out.append(line)
            fence = _fence(line)
            if (
                fence is not None
                and fence[0][0] == open_fence[0]
                and len(fence[0]) >= len(open_fence)
                and not fence[1].strip()
            ):
                open_fence = None
            continue
        if not in_comment and (fence := _fence(line)) is not None:
            open_fence = fence[0]
            out.append(line)
            continue
        text, in_comment, had_comment = _strip_line(line, in_comment)
        if had_comment and not text.strip():
            continue
        out.append(text)
    return "".join(out), in_comment
