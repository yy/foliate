"""Markdown processing utilities for foliate."""

import re
from functools import lru_cache
from pathlib import Path

import frontmatter
import markdown

# Markdown extensions configuration
MARKDOWN_EXTENSIONS = [
    "codehilite",
    "markdown_katex",
    "mdx_wikilink_plus",
    "mdx_linkify",
    "extra",  # tables, footnotes, etc.
    "smarty",
    "sane_lists",
    "toc",
    "foliate.obsidian_image_size",
]

EXTENSION_CONFIGS = {
    "markdown_katex": {
        "insert_fonts_css": True,
        "no_inline_svg": False,
    },
    "mdx_wikilink_plus": {
        # base_url is set dynamically
        "end_url": "/",
        "url_whitespace": " ",
        "label_case": "none",
    },
    "codehilite": {
        "css_class": "highlight",
        "guess_lang": False,
    },
    "toc": {
        "permalink": "#",
        "permalink_class": "header-anchor",
        "permalink_title": "Link to this section",
    },
}

# Compiled patterns for extract_description (ordered by application)
_DESCRIPTION_PATTERNS = [
    # Remove YAML frontmatter
    (re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL), ""),
    # Remove code blocks
    (re.compile(r"```.*?```", re.DOTALL), ""),
    (re.compile(r"`[^`]+`"), ""),
    # Remove images
    (re.compile(r"!\[.*?\]\(.*?\)"), ""),
    # Remove links but keep text
    (re.compile(r"\[([^\]]+)\]\([^\)]+\)"), r"\1"),
    # Remove wikilinks but keep text
    (re.compile(r"\[\[([^\]]+)\]\]"), r"\1"),
    # Remove headers
    (re.compile(r"^#+\s+", re.MULTILINE), ""),
    # Remove bold/italic markers
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"\*([^*]+)\*"), r"\1"),
    (re.compile(r"__([^_]+)__"), r"\1"),
    (re.compile(r"_([^_]+)_"), r"\1"),
    # Remove blockquotes
    (re.compile(r"^>\s*", re.MULTILINE), ""),
    # Remove horizontal rules
    (re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE), ""),
    # Remove HTML tags
    (re.compile(r"<[^>]+>"), ""),
    # Remove math blocks
    (re.compile(r"\$\$.*?\$\$", re.DOTALL), ""),
    (re.compile(r"\$[^$]+\$"), ""),
]
_WHITESPACE_PATTERN = re.compile(r"\s+")


def extract_description(markdown_content: str, max_length: int = 160) -> str:
    """Extract a plain text description from markdown content.

    Args:
        markdown_content: Raw markdown text
        max_length: Maximum character length for description

    Returns:
        Plain text description string
    """
    if not markdown_content:
        return ""

    content = markdown_content

    # Apply all stripping patterns
    for pattern, replacement in _DESCRIPTION_PATTERNS:
        content = pattern.sub(replacement, content)

    # Normalize whitespace
    content = _WHITESPACE_PATTERN.sub(" ", content).strip()

    # Get first meaningful paragraph (at least 50 chars)
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    for para in paragraphs:
        if len(para) >= 50:
            content = para
            break
    else:
        content = paragraphs[0] if paragraphs else ""

    # Truncate to max length at word boundary
    if len(content) > max_length:
        content = content[: max_length - 3].rsplit(" ", 1)[0] + "..."

    return content


def extract_first_image(markdown_content: str) -> str | None:
    """Extract the first image URL from markdown content.

    Args:
        markdown_content: Raw markdown text

    Returns:
        Image URL string or None if no image found
    """
    if not markdown_content:
        return None

    # Match markdown images: ![alt](url)
    match = re.search(r"!\[[^\]]*\]\(([^\)]+)\)", markdown_content)
    if match:
        return match.group(1)

    # Match HTML images: <img src="url">
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', markdown_content)
    if match:
        return match.group(1)

    return None


def parse_markdown_file(filepath: Path) -> tuple[dict, str]:
    """Parse a markdown file with YAML frontmatter.

    Args:
        filepath: Path to the markdown file

    Returns:
        Tuple of (metadata dict, markdown content string)
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)
        return dict(post.metadata), post.content
    except Exception as e:
        print(f"Warning: YAML parsing error in {filepath}: {e}")
        return {}, ""


@lru_cache(maxsize=8)
def get_markdown_converter(base_url: str) -> markdown.Markdown:
    """Get or create a cached Markdown converter for the given base_url."""

    extension_configs = {k: v.copy() for k, v in EXTENSION_CONFIGS.items()}
    extension_configs["mdx_wikilink_plus"] = extension_configs[
        "mdx_wikilink_plus"
    ].copy()
    extension_configs["mdx_wikilink_plus"]["base_url"] = base_url

    return markdown.Markdown(
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=extension_configs,
    )


def render_markdown(content: str, base_url: str = "/wiki/") -> str:
    """Render markdown to HTML with extensions.

    Args:
        content: Markdown content
        base_url: Base URL for wikilinks

    Returns:
        HTML string
    """
    md = get_markdown_converter(base_url)
    md.reset()

    html_content = md.convert(content)

    # Process asset paths to ensure they work with site structure
    html_content = process_asset_paths(html_content)

    # Fix wikilinks from homepage content to wiki pages
    if base_url == "/":
        html_content = fix_homepage_to_wiki_links(html_content)

    return html_content


def process_asset_paths(html_content: str) -> str:
    """Convert relative asset paths to absolute paths."""
    return re.sub(r"""((?:src|href)=["'])assets/""", r"\1/assets/", html_content)


def fix_homepage_to_wiki_links(html_content: str) -> str:
    """Fix wikilinks from homepage content to point to wiki pages.

    Links starting with / that aren't wiki/, assets/, or external URLs
    get prefixed with /wiki to point to the wiki section.
    """
    skip_prefixes = ("wiki/", "assets/", "http://", "https://", "#", "mailto:")

    def should_be_wiki_link(path: str) -> bool:
        clean_path = path.strip("/")
        if not clean_path:
            return False
        if clean_path.startswith(skip_prefixes):
            return False
        return True

    def replace_link(match):
        link_path = match.group(1)
        if should_be_wiki_link(link_path):
            return f'href="/wiki{link_path}"'
        return match.group(0)

    return re.sub(r'href="(/[^"]*?)"', replace_link, html_content)
