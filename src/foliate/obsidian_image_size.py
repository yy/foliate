#!/usr/bin/env python3
"""
Markdown extension to handle Obsidian-style image size modifiers.
Converts ![|width](url) to <img src="url" width="width">
"""

import html
import re

from markdown import Extension
from markdown.preprocessors import Preprocessor

# Pattern to match ![alt|width](url) or ![|width](url)
OBSIDIAN_IMAGE_PATTERN = re.compile(r"!\[([^|\]]*)\|(\d+)\]\(([^)]+)\)")


class ObsidianImageSizePreprocessor(Preprocessor):
    """Preprocessor to handle Obsidian-style image size syntax."""

    def run(self, lines):
        """Process lines to convert Obsidian image syntax to standard markdown."""
        new_lines = []

        for line in lines:
            new_line = OBSIDIAN_IMAGE_PATTERN.sub(self._replace_image, line)
            new_lines.append(new_line)

        return new_lines

    def _replace_image(self, match):
        """Replace Obsidian image syntax with HTML img tag."""
        alt_text = html.escape(match.group(1).strip())
        width = match.group(2)  # digits only from regex, safe
        url = html.escape(match.group(3))

        return f'<img src="{url}" alt="{alt_text}" width="{width}">'


class ObsidianImageSizeExtension(Extension):
    """Markdown extension for Obsidian image size syntax."""

    def extendMarkdown(self, md):
        """Register the preprocessor with markdown."""
        processor = ObsidianImageSizePreprocessor(md)
        processor.priority = 175  # Run before other preprocessors
        md.preprocessors.register(processor, "obsidian_image_size", 175)


def makeExtension(**kwargs):
    """Entry point for markdown extension."""
    return ObsidianImageSizeExtension(**kwargs)
