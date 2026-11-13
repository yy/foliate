"""Markdown extension for Obsidian callouts.

    > [!note]- Derivation      -> <details class="callout callout-note">
    > [!tip]+ Open by default  -> <details class="callout callout-tip" open>
    > [!warning] Heads up      -> <div class="callout callout-warning">

The callout header must be the first line of a blockquote. The type is
case-insensitive; a missing title falls back to the capitalized type, as in
Obsidian. The body is parsed as ordinary Markdown, so lists, math, wikilinks,
and nested callouts all work. Blockquotes without a header are untouched.
"""

import re
import xml.etree.ElementTree as etree

from markdown import Extension
from markdown.blockprocessors import BlockQuoteProcessor

# Header on the first quoted line: [!type], optional fold marker, optional title.
_HEADER_RE = re.compile(r"^\[!([^\]\s]+)\]([+-]?)(?:[ \t]+(.*?))?[ \t]*$")
_UNSAFE_CLASS_CHARS = re.compile(r"[^a-z0-9_-]+")


class CalloutProcessor(BlockQuoteProcessor):
    """Turn a blockquote whose first line is ``[!type]`` into a callout."""

    def _split(self, block: str) -> tuple[re.Match[str], re.Match[str]] | None:
        quote = self.RE.search(block)
        if quote is None:
            return None
        header = _HEADER_RE.match(quote.group(2))
        return (quote, header) if header else None

    def test(self, parent: etree.Element, block: str) -> bool:
        return super().test(parent, block) and self._split(block) is not None

    def run(self, parent: etree.Element, blocks: list[str]) -> None:
        block = blocks.pop(0)
        split = self._split(block)
        assert split is not None  # test() guarantees a header
        quote, header = split

        # Lines before the callout (a paragraph it interrupts) parse first.
        self.parser.parseBlocks(parent, [block[: quote.start()]])

        callout_type, fold, title = header.groups()
        callout_type = callout_type.lower()
        css_type = _UNSAFE_CLASS_CHARS.sub("-", callout_type)
        title = title or callout_type.capitalize()

        if fold:
            callout = etree.SubElement(parent, "details")
            if fold == "+":
                callout.set("open", "")
            heading = etree.SubElement(callout, "summary")
        else:
            callout = etree.SubElement(parent, "div")
            heading = etree.SubElement(callout, "div")
        callout.set("class", f"callout callout-{css_type}")
        heading.set("class", "callout-title")
        heading.text = title

        body_lines = block[quote.end() :].split("\n")[1:]
        if any(line.strip() for line in body_lines):
            body = etree.SubElement(callout, "div")
            body.set("class", "callout-content")
            self.parser.state.set("blockquote")
            self.parser.parseChunk(
                body, "\n".join(self.clean(line) for line in body_lines)
            )
            self.parser.state.reset()


class CalloutExtension(Extension):
    """Register the callout block processor ahead of plain blockquotes."""

    def extendMarkdown(self, md) -> None:
        # Plain blockquotes are priority 20; claim callout blocks first.
        md.parser.blockprocessors.register(
            CalloutProcessor(md.parser), "foliate_callout", 21
        )


def makeExtension(**kwargs) -> CalloutExtension:  # noqa: N802
    """Entry point for python-markdown extension loading."""
    return CalloutExtension(**kwargs)
