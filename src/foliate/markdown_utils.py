"""Markdown processing utilities for foliate."""

import re
import threading
from pathlib import Path

import frontmatter
import markdown
from bs4 import BeautifulSoup

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
    # Remove wikilinks but keep visible text
    (re.compile(r"\[\[[^\]|]+\|([^\]]+)\]\]"), r"\1"),
    (re.compile(r"\[\[([^#\]]+)#[^\]]+\]\]"), r"\1"),
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
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")
_MARKDOWN_CONVERTERS = threading.local()
_NL2BR_ENABLED = False
_SLUGIFY_URLS_ENABLED = False
_WIKI_BASE_URL = "/wiki/"


def _disable_markdown_katex_npx_probe() -> None:
    """Prevent markdown-katex from shelling out to interactive npx probes.

    markdown-katex checks PATH for both `katex` and `npx --no-install katex`.
    In direct CLI environments, the npx probe can block waiting for input even
    when the page contains no math. Keep direct katex executables discoverable,
    but drop the npx fallback so plain markdown builds stay non-blocking.
    """
    try:
        from markdown_katex import wrapper  # type: ignore[import-untyped]
    except ImportError:
        return

    if getattr(wrapper, "_foliate_npx_probe_disabled", False):
        return

    original_get_local_bin_candidates = wrapper._get_local_bin_candidates

    def _get_local_bin_candidates_without_npx() -> list[str]:
        return [
            candidate
            for candidate in original_get_local_bin_candidates()
            if Path(candidate.split()[0]).stem.lower() != "npx"
        ]

    wrapper._get_local_bin_candidates = _get_local_bin_candidates_without_npx
    wrapper._foliate_npx_probe_disabled = True


def slugify_path(path: str) -> str:
    """Replace spaces with hyphens in each segment of a URL path.

    Preserves case and special characters; only transforms spaces.

    Examples:
        >>> slugify_path("Accessible PDF from LaTeX")
        'Accessible-PDF-from-LaTeX'
        >>> slugify_path("A/B  C/D")
        'A/B-C/D'
    """
    parts = path.split("/")
    return "/".join(_MULTI_HYPHEN_RE.sub("-", part.replace(" ", "-")) for part in parts)


def configure_extensions(
    nl2br: bool = False,
    slugify_urls: bool = False,
    wiki_base_url: str = "/wiki/",
) -> None:
    """Configure markdown extensions and clear converter caches.

    Call this at the start of a build to set up extensions based on config.
    Clears the thread-local converter cache so converters are rebuilt.
    """
    global _NL2BR_ENABLED, _SLUGIFY_URLS_ENABLED, _WIKI_BASE_URL  # noqa: PLW0603
    _NL2BR_ENABLED = nl2br
    _SLUGIFY_URLS_ENABLED = slugify_urls
    _WIKI_BASE_URL = wiki_base_url
    # Clear thread-local converter cache so converters pick up new extensions
    cache = getattr(_MARKDOWN_CONVERTERS, "cache", None)
    if cache is not None:
        cache.clear()


def _get_extensions() -> list[str]:
    """Return the current extensions list, optionally including nl2br."""
    if _NL2BR_ENABLED:
        return ["nl2br", *MARKDOWN_EXTENSIONS]
    return list(MARKDOWN_EXTENSIONS)


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

    # Match markdown images: ![alt](url "optional title")
    match = re.search(r"!\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)", markdown_content)
    if match:
        url = match.group(1).strip()
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]
        return url

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
    if _SLUGIFY_URLS_ENABLED:
        extension_configs["mdx_wikilink_plus"]["url_whitespace"] = "-"
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

    _disable_markdown_katex_npx_probe()
    converter = markdown.Markdown(
        extensions=_get_extensions(),
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
        html_content = fix_homepage_to_wiki_links(
            html_content, wiki_base_url=_WIKI_BASE_URL
        )

    return html_content


def process_asset_paths(html_content: str) -> str:
    """Convert relative asset paths to absolute paths."""
    return re.sub(r"""((?:src|href)=["'])assets/""", r"\1/assets/", html_content)


def fix_homepage_to_wiki_links(
    html_content: str,
    wiki_base_url: str = "/wiki/",
) -> str:
    """Fix wikilinks from homepage content to point to wiki pages.

    Only wikilink anchors are rewritten. Regular absolute links like /about/
    should continue to point to the site root.
    """
    normalized_wiki_base = wiki_base_url.rstrip("/")
    soup = BeautifulSoup(html_content, "html.parser")

    for link in soup.find_all("a", class_="wikilink"):
        href = link.get("href")
        if (
            not isinstance(href, str)
            or not href.startswith("/")
            or href.startswith("//")
        ):
            continue
        if not normalized_wiki_base:
            continue
        if href == normalized_wiki_base or href.startswith(normalized_wiki_base + "/"):
            continue
        link["href"] = f"{normalized_wiki_base}{href}"

    return str(soup)
