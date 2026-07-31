"""Markdown extension to auto-link bare URLs with an explicit scheme.

Replaces mdx-linkify/bleach (both unmaintained). Bleach's linkifier relied on
a pre-2013 TLD list, so URLs on modern TLDs (.dev, .app, .google, ...) were
left as plain text. An explicit http(s):// scheme is a strong enough signal on
its own, so this extension links any scheme-prefixed URL and needs no TLD list.
Schemeless text like ``example.dev`` is intentionally not linked.
"""

import re
import xml.etree.ElementTree as etree

from markdown import Extension
from markdown.treeprocessors import Treeprocessor

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Elements whose text must never be linkified.
SKIP_TAGS = frozenset({"a", "code", "pre", "script", "style"})

# Sentence punctuation that commonly trails a URL but is not part of it.
_TRAILING_CHARS = ".,;:!?'\""


def _trim_url(url: str) -> str:
    """Strip trailing punctuation and unbalanced closing parens from a match."""
    while url:
        if url[-1] in _TRAILING_CHARS:
            url = url[:-1]
        elif url[-1] == ")" and url.count(")") > url.count("("):
            url = url[:-1]
        else:
            break
    return url


def _split_links(text: str) -> tuple[str, list[etree.Element]] | None:
    """Split text containing URLs into (leading text, anchor elements).

    Each returned <a> element carries the text following its URL in its tail.
    Returns None when the text contains no URL.
    """
    segments: list[tuple[str, str]] = []  # (text before URL, URL)
    last = 0
    for match in URL_PATTERN.finditer(text):
        url = _trim_url(match.group())
        if not url:
            continue
        segments.append((text[last : match.start()], url))
        last = match.start() + len(url)
    if not segments:
        return None

    elements: list[etree.Element] = []
    for before, url in segments:
        if elements:
            elements[-1].tail = before
        anchor = etree.Element("a")
        anchor.set("href", url)
        anchor.set("rel", "nofollow")
        anchor.text = url
        elements.append(anchor)
    elements[-1].tail = text[last:]
    return segments[0][0], elements


class AutolinkTreeprocessor(Treeprocessor):
    """Wrap bare scheme-prefixed URLs in anchor elements."""

    def run(self, root: etree.Element) -> None:
        self._process(root)

    def _process(self, parent: etree.Element) -> None:
        for child in list(parent):
            if child.tag not in SKIP_TAGS:
                self._process(child)

        if parent.tag in SKIP_TAGS:
            return

        if parent.text:
            split = _split_links(parent.text)
            if split:
                parent.text, elements = split
                for i, element in enumerate(elements):
                    parent.insert(i, element)

        for child in list(parent):
            if not child.tail:
                continue
            split = _split_links(child.tail)
            if split:
                child.tail, elements = split
                position = list(parent).index(child) + 1
                for i, element in enumerate(elements):
                    parent.insert(position + i, element)


class AutolinkExtension(Extension):
    """Markdown extension for auto-linking bare URLs."""

    def extendMarkdown(self, md):
        # Low priority: run after inline processing so code spans and existing
        # anchors are real elements that SKIP_TAGS can exclude.
        md.treeprocessors.register(AutolinkTreeprocessor(md), "foliate_autolink", 2)


def makeExtension(**kwargs):
    """Entry point for markdown extension."""
    return AutolinkExtension(**kwargs)
