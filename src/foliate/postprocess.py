"""Post-processing for foliate static site generation.

Sanitizes wikilinks in generated HTML files:
- Removes links to private (non-public) pages, converting them to plain text
  markers that can be restored later if the page becomes public
- Cleans escaped dollar signs to prevent KaTeX processing issues
"""

from pathlib import Path

from bs4 import BeautifulSoup

from .config import Config
from .markdown_utils import slugify_path  # noqa: F401
from .page import Page


def extract_wiki_path(href: str, wiki_prefix: str = "wiki") -> str | None:
    """Extract page path from wiki href like '/wiki/PageName/' -> 'PageName'."""
    if not href:
        return None

    # Strip fragment (anchor) before extracting path
    href = href.split("#", 1)[0]

    if wiki_prefix:
        prefix = f"/{wiki_prefix}/"
        if not href.startswith(prefix):
            return None

        # Remove prefix and trailing '/'
        path = href[len(prefix) :]
    else:
        # Root wiki mode: page links are like '/PageName/'.
        if not href.startswith("/") or href.startswith("//"):
            return None
        path = href[1:]

    if path.endswith("/"):
        path = path[:-1]

    return path if path else None


def sanitize_wikilinks(
    html_content: str,
    public_pages: set[str],
    wiki_prefix: str = "wiki",
    slug_to_original: dict[str, str] | None = None,
) -> tuple[str, bool, int, bool]:
    """Remove wikilinks to private pages and restore previously private links.

    Args:
        html_content: HTML content to process
        public_pages: Set of public page paths
        wiki_prefix: URL prefix for wiki content
        slug_to_original: Mapping from slugified paths to original page paths
            (used when slugify_urls is enabled)

    Returns:
        Tuple of (sanitized_content, was_modified, removed_links_count, cleaned_dollars)
    """
    from bs4 import NavigableString

    from .logging import debug

    def _resolve_target(target: str) -> str | None:
        """Resolve a target from an href to the original page path."""
        if target in public_pages:
            return target
        if slug_to_original and target in slug_to_original:
            return slug_to_original[target]
        return None

    soup = BeautifulSoup(html_content, "html.parser")
    modified = False
    removed_links_count = 0

    # Restore previously sanitized private links if target pages are now public.
    private_spans = soup.find_all("span", class_="wikilink-private")
    for span in private_spans:
        wiki_path_attr = span.get("data-wiki-path", "")
        wiki_path = wiki_path_attr if isinstance(wiki_path_attr, str) else ""
        if wiki_path and wiki_path in public_pages:
            url_path = slugify_path(wiki_path) if slug_to_original else wiki_path
            href = f"/{wiki_prefix}/{url_path}/" if wiki_prefix else f"/{url_path}/"
            span.name = "a"
            span.attrs.clear()
            span["class"] = "wikilink"
            span["href"] = href
            span["rel"] = "nofollow"
            modified = True

    # Find all wikilinks
    wikilinks = soup.find_all("a", class_="wikilink")

    for link in wikilinks:
        href_attr = link.get("href", "")
        href = href_attr if isinstance(href_attr, str) else ""
        wiki_target = extract_wiki_path(href, wiki_prefix)

        if wiki_target and _resolve_target(wiki_target) is None:
            # This is a link to a private page.
            # Store original path for data-wiki-path so restore works later.
            original_path = wiki_target
            if slug_to_original and wiki_target in slug_to_original:
                original_path = slug_to_original[wiki_target]
            debug(f"    Removed private link: {wiki_target} -> {link.get_text()}")
            link.name = "span"
            link.attrs.clear()
            link["class"] = "wikilink-private"
            link["data-wiki-path"] = original_path
            modified = True
            removed_links_count += 1

    # Clean up escaped dollar signs in text nodes only (not in script/style tags)
    cleaned_dollars = False
    for text_node in soup.find_all(string=lambda t: t and "\\$" in t):
        # Skip script and style tags
        parent = text_node.parent
        if parent is not None and parent.name in ("script", "style", "code", "pre"):
            continue
        new_text = text_node.replace("\\$", "$")
        text_node.replace_with(NavigableString(new_text))
        modified = True
        cleaned_dollars = True

    if cleaned_dollars:
        debug("    Cleaned escaped dollar signs")

    return str(soup), modified, removed_links_count, cleaned_dollars


def process_html_file(
    html_file: Path,
    public_pages: set[str],
    wiki_prefix: str = "wiki",
    build_dir: Path | None = None,
    slug_to_original: dict[str, str] | None = None,
) -> bool:
    """Process a single HTML file to sanitize wikilinks.

    Args:
        html_file: Path to HTML file
        public_pages: Set of public page paths
        wiki_prefix: URL prefix for wiki content
        build_dir: Build directory for computing relative paths
        slug_to_original: Mapping from slugified paths to original page paths

    Returns:
        True if file was modified, False otherwise
    """
    from .logging import debug, error

    try:
        content = html_file.read_text(encoding="utf-8")

        sanitized_content, modified, removed_links_count, cleaned_dollars = (
            sanitize_wikilinks(content, public_pages, wiki_prefix, slug_to_original)
        )

        if modified:
            html_file.write_text(sanitized_content, encoding="utf-8")

            # Build a concise summary
            changes = []
            if removed_links_count > 0:
                changes.append(f"{removed_links_count} private links")
            if cleaned_dollars:
                changes.append("escaped $")
            change_summary = f" ({', '.join(changes)})" if changes else ""
            # Show relative path from build dir, or parent folder name
            if build_dir:
                display_path = str(html_file.parent.relative_to(build_dir))
            else:
                display_path = html_file.parent.name
            debug(f"  Sanitized: {display_path}{change_summary}")
            return True
        return False

    except Exception as e:
        error(f"Processing {html_file}: {e}")
        return False


def postprocess_links(
    config: Config,
    public_pages: list[Page],
    single_page: str | None = None,
) -> bool:
    """Post-process HTML files to sanitize wikilinks.

    Args:
        config: Foliate configuration
        public_pages: List of public pages from build
        single_page: If specified, only process this page (used in watch mode)

    Returns:
        True if successful, False otherwise
    """
    from .logging import debug, error, warning

    build_dir = config.get_build_dir()
    wiki_prefix = config.build.wiki_prefix.strip("/")

    if not build_dir.exists():
        error(f"Build directory '{build_dir}' does not exist")
        return False

    # Extract public page paths into a set for fast lookup
    public_paths = {page.path for page in public_pages}

    # Build slug-to-original mapping when slugify is enabled
    slugify = config.build.slugify_urls
    slug_to_original: dict[str, str] | None = None
    if slugify:
        slug_to_original = {
            slugify_path(p): p for p in public_paths if slugify_path(p) != p
        }

    if not single_page:
        debug(f"Post-processing with {len(public_paths)} public pages...")

    # Find HTML files to process
    html_files: list[Path] = []

    if single_page:
        # Process only the specified page
        sp = slugify_path(single_page) if slugify else single_page
        possible_paths = [
            build_dir / wiki_prefix / sp / "index.html",  # Wiki page
            build_dir / sp / "index.html",  # Homepage page
        ]

        for path in possible_paths:
            if path.exists():
                html_files.append(path)
                break

        if not html_files:
            warning(f"Could not find HTML file for page '{single_page}'")
            return False
    else:
        # Find all HTML files in the build directory (excluding static)
        for html_file in build_dir.glob("**/index.html"):
            relative_path = html_file.relative_to(build_dir)
            if not str(relative_path).startswith("static/"):
                html_files.append(html_file)

        debug(f"  Processing {len(html_files)} HTML files...")

    modified_count = 0
    for html_file in html_files:
        if process_html_file(
            html_file, public_paths, wiki_prefix, build_dir, slug_to_original
        ):
            modified_count += 1

    if not single_page:
        debug(f"  Post-processing complete: {modified_count} files modified")

    return True
