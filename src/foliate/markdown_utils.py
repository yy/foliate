"""Markdown processing utilities for foliate."""

import re
import threading
from pathlib import Path

import frontmatter
import markdown

type ExtensionConfigMap = dict[str, dict[str, object]]

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

EXTENSION_CONFIGS: ExtensionConfigMap = {
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
_MARKDOWN_CONVERTERS = threading.local()


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

    # Get first meaningful paragraph (at least 50 chars)
    paragraphs = []
    for para in re.split(r"\n\s*\n+", content):
        cleaned = _WHITESPACE_PATTERN.sub(" ", para).strip()
        if cleaned:
            paragraphs.append(cleaned)

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


def parse_markdown_file(filepath: Path) -> tuple[dict[str, object], str]:
    """Parse a markdown file with YAML frontmatter.

    Args:
        filepath: Path to the markdown file

    Returns:
        Tuple of (metadata dict, markdown content string)
    """
    try:
        with filepath.open("r", encoding="utf-8") as f:
            post = frontmatter.load(f)
        return dict(post.metadata), post.content
    except Exception as e:
        from .logging import warning

        warning(f"YAML parsing error in {filepath}: {e}")
        return {}, ""


def _build_extension_configs(base_url: str) -> ExtensionConfigMap:
    """Build Markdown extension configs for the given base_url."""

    extension_configs = {k: v.copy() for k, v in EXTENSION_CONFIGS.items()}
    extension_configs["mdx_wikilink_plus"]["base_url"] = base_url
    return extension_configs


def _get_thread_local_converter_cache() -> dict[str, markdown.Markdown]:
    cache = getattr(_MARKDOWN_CONVERTERS, "cache", None)
    if cache is None:
        cache = {}
        _MARKDOWN_CONVERTERS.cache = cache
    return cache


def get_markdown_converter(base_url: str) -> markdown.Markdown:
    """Get a thread-local Markdown converter for the given base_url.

    Markdown converter construction is expensive, especially with the KaTeX
    extension. Reuse a converter per thread/base_url and reset it before each
    conversion so watch-mode rebuild threads do not share mutable parser state.
    """
    cache = _get_thread_local_converter_cache()
    cached = cache.get(base_url)
    if cached is not None:
        return cached

    converter = markdown.Markdown(
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=_build_extension_configs(base_url),
    )
    cache[base_url] = converter
    return converter


_WIKILINK_BACKTICK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _strip_backticks_in_wikilink_targets(content: str) -> str:
    """Strip backticks from wikilink targets to prevent markdown code interference.

    Markdown's inline code processor runs before the wikilink extension and
    replaces backtick-wrapped text with placeholders, mangling the link target.
    """

    def _replace(match: re.Match) -> str:
        inner = match.group(1)
        if "|" in inner:
            target, display = inner.split("|", 1)
            return f"[[{target.replace('`', '')}|{display}]]"
        return f"[[{inner.replace('`', '')}]]"

    return _WIKILINK_BACKTICK_RE.sub(_replace, content)


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
    content = _strip_backticks_in_wikilink_targets(content)
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
    skip_prefixes = (
        "wiki/",
        "assets/",
        "static/",
        "http://",
        "https://",
        "#",
        "mailto:",
    )

    def should_be_wiki_link(path: str) -> bool:
        clean_path = path.strip("/")
        if not clean_path:
            return False
        if clean_path.startswith(skip_prefixes):
            return False
        # Skip paths with file extensions (e.g., feed.xml, robots.txt)
        if "." in clean_path.split("/")[-1]:
            return False
        return True

    def replace_link(match: re.Match[str]) -> str:
        link_path = match.group("double_quoted_path") or match.group(
            "single_quoted_path"
        )
        quote = '"' if match.group("double_quoted_path") else "'"
        if should_be_wiki_link(link_path):
            return f"href={quote}/wiki{link_path}{quote}"
        return match.group(0)

    return re.sub(
        r"""href="(?P<double_quoted_path>/[^"]*?)"|href='(?P<single_quoted_path>/[^']*?)'""",
        replace_link,
        html_content,
    )
