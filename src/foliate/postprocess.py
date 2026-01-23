"""Post-processing for foliate static site generation.

Sanitizes wikilinks in generated HTML files:
- Removes links to private (non-public) pages, converting them to plain text
- Cleans escaped dollar signs to prevent KaTeX processing issues
"""

from pathlib import Path

from bs4 import BeautifulSoup

from .config import Config


def extract_wiki_path(href: str, wiki_prefix: str = "wiki") -> str | None:
    """Extract page path from wiki href like '/wiki/PageName/' -> 'PageName'."""
    if not href:
        return None

    prefix = f"/{wiki_prefix}/"
    if not href.startswith(prefix):
        return None

    # Remove prefix and trailing '/'
    path = href[len(prefix) :]
    if path.endswith("/"):
        path = path[:-1]

    return path if path else None


def sanitize_wikilinks(
    html_content: str,
    public_pages: set[str],
    wiki_prefix: str = "wiki",
    verbose: bool = False,
) -> tuple[str, bool, int, bool]:
    """Remove wikilinks to private pages, convert to plain text.

    Args:
        html_content: HTML content to process
        public_pages: Set of public page paths
        wiki_prefix: URL prefix for wiki content
        verbose: Enable verbose output

    Returns:
        Tuple of (sanitized_content, was_modified, removed_links_count, cleaned_dollars)
    """
    from bs4 import NavigableString

    soup = BeautifulSoup(html_content, "html.parser")
    modified = False
    removed_links_count = 0

    # Find all wikilinks
    wikilinks = soup.find_all("a", class_="wikilink")

    for link in wikilinks:
        href = link.get("href", "")
        wiki_path = extract_wiki_path(href, wiki_prefix)

        if wiki_path and wiki_path not in public_pages:
            # This is a link to a private page - unwrap to preserve inner HTML
            if verbose:
                print(f"    Removed private link: {wiki_path} -> {link.get_text()}")
            link.unwrap()
            modified = True
            removed_links_count += 1

    # Clean up escaped dollar signs in text nodes only (not in script/style tags)
    cleaned_dollars = False
    for text_node in soup.find_all(string=lambda t: t and "\\$" in t):
        # Skip script and style tags
        if text_node.parent.name in ("script", "style", "code", "pre"):
            continue
        new_text = text_node.replace("\\$", "$")
        text_node.replace_with(NavigableString(new_text))
        modified = True
        cleaned_dollars = True

    if cleaned_dollars and verbose:
        print("    Cleaned escaped dollar signs")

    return str(soup), modified, removed_links_count, cleaned_dollars


def process_html_file(
    html_file: Path,
    public_pages: set[str],
    wiki_prefix: str = "wiki",
    verbose: bool = False,
) -> bool:
    """Process a single HTML file to sanitize wikilinks.

    Args:
        html_file: Path to HTML file
        public_pages: Set of public page paths
        wiki_prefix: URL prefix for wiki content
        verbose: Enable verbose output

    Returns:
        True if file was modified, False otherwise
    """
    try:
        content = html_file.read_text(encoding="utf-8")

        sanitized_content, modified, removed_links_count, cleaned_dollars = (
            sanitize_wikilinks(content, public_pages, wiki_prefix, verbose)
        )

        if modified:
            html_file.write_text(sanitized_content, encoding="utf-8")

            # Build a concise summary for non-verbose mode
            if not verbose:
                changes = []
                if removed_links_count > 0:
                    changes.append(f"{removed_links_count} private links")
                if cleaned_dollars:
                    changes.append("escaped $")
                change_summary = f" ({', '.join(changes)})" if changes else ""
                print(f"  Sanitized: {html_file.name}{change_summary}")
            return True
        return False

    except Exception as e:
        print(f"  Error processing {html_file}: {e}")
        return False


def postprocess_links(
    config: Config,
    public_pages: list[dict],
    verbose: bool = False,
    single_page: str | None = None,
) -> bool:
    """Post-process HTML files to sanitize wikilinks.

    Args:
        config: Foliate configuration
        public_pages: List of public page dicts from build
        verbose: Whether to print detailed messages
        single_page: If specified, only process this page (used in watch mode)

    Returns:
        True if successful, False otherwise
    """
    build_dir = config.get_build_dir()
    wiki_prefix = config.build.wiki_prefix.strip("/")

    if not build_dir.exists():
        print(f"Error: Build directory '{build_dir}' does not exist")
        return False

    # Extract public page paths into a set for fast lookup
    public_paths = {page["path"] for page in public_pages}

    if not single_page and verbose:
        print(f"Post-processing with {len(public_paths)} public pages...")

    # Find HTML files to process
    html_files: list[Path] = []

    if single_page:
        # Process only the specified page
        possible_paths = [
            build_dir / wiki_prefix / single_page / "index.html",  # Wiki page
            build_dir / single_page / "index.html",  # Homepage page
        ]

        for path in possible_paths:
            if path.exists():
                html_files.append(path)
                break

        if not html_files:
            if verbose:
                print(f"  Warning: Could not find HTML file for page '{single_page}'")
            return False
    else:
        # Find all HTML files in the build directory (excluding static)
        for html_file in build_dir.glob("**/index.html"):
            relative_path = html_file.relative_to(build_dir)
            if not str(relative_path).startswith("static/"):
                html_files.append(html_file)

        if verbose:
            print(f"  Processing {len(html_files)} HTML files...")

    modified_count = 0
    for html_file in html_files:
        if process_html_file(html_file, public_paths, wiki_prefix, verbose):
            modified_count += 1

    if not single_page and verbose:
        print(f"  Post-processing complete: {modified_count} files modified")

    return True
