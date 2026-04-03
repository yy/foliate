"""Atom feed generation for foliate."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

# Re-export FeedConfig from config for convenience
from .config import FeedConfig
from .markdown_utils import render_markdown
from .page import Page
from .page import parse_frontmatter_date as parse_frontmatter_date

if TYPE_CHECKING:
    from jinja2 import Environment

    from .config import Config

__all__ = ["FeedConfig", "FeedItem", "generate_feed"]


@dataclass
class FeedItem:
    """A single item in a feed."""

    title: str
    url: str
    content: str
    published: datetime
    updated: datetime
    summary: str | None = None


def format_atom_date(dt: datetime) -> str:
    """Format datetime as RFC 3339 for Atom.

    Args:
        dt: datetime object (should be in UTC)

    Returns:
        RFC 3339 formatted string like "2024-03-15T10:30:00Z"
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_pages(
    pages: list[Page],
    window_days: int,
    now: datetime | None = None,
) -> tuple[list[Page], list[Page]]:
    """Classify pages into 'new' and 'updated' categories.

    Args:
        pages: List of Page objects
        window_days: Number of days to look back
        now: Current datetime (for testing), defaults to now

    Returns:
        (new_pages, updated_pages) - both sorted by date descending
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_start = now - timedelta(days=window_days)
    new_pages: list[Page] = []
    updated_pages: list[Page] = []

    for page in pages:
        published = page.published_at
        modified = page.modified_at

        if published is None:
            continue

        # Is the page "new" (published within window)?
        is_new = published >= window_start

        if is_new:
            new_pages.append(page)
        elif modified and modified >= window_start:
            # Page was published before window but modified within
            updated_pages.append(page)
        # else: page is outside window entirely, skip

    # Sort by date descending, then by path ascending for deterministic order
    new_pages.sort(key=lambda p: (-(p.published_at or now).timestamp(), p.path))
    updated_pages.sort(key=lambda p: (-(p.modified_at or now).timestamp(), p.path))

    return new_pages, updated_pages


def extract_summary(html: str, max_length: int = 300) -> str:
    """Extract a plain text summary from HTML.

    Extracts the first paragraph and truncates if needed.

    Args:
        html: HTML content
        max_length: Maximum length of summary

    Returns:
        Plain text summary
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Find first paragraph
    first_p = soup.find("p")
    if first_p:
        text = first_p.get_text()
    else:
        text = soup.get_text()

    text = text.strip()

    if len(text) > max_length:
        return text[:max_length] + "..."

    return text


def generate_updates_digest(pages: list[Page], site_url: str) -> str:
    """Generate HTML content for the updates digest entry.

    Args:
        pages: List of updated pages
        site_url: Base URL of the site

    Returns:
        HTML string with list of updated pages
    """
    if not pages:
        return ""

    lines = ["<p>The following pages were recently updated:</p>", "<ul>"]

    for page in pages:
        title = escape(page.title)
        url = escape(f"{site_url}{page.url}", quote=True)
        date_str = page.modified_at.strftime("%Y-%m-%d") if page.modified_at else ""

        lines.append(f'  <li><a href="{url}">{title}</a> - {date_str}</li>')

    lines.append("</ul>")
    return "\n".join(lines)


def create_feed_items(
    pages: list[Page],
    site_url: str,
    full_content: bool,
    max_items: int,
) -> list[FeedItem]:
    """Create FeedItem objects from pages.

    Args:
        pages: List of Page objects
        site_url: Base URL of the site
        full_content: Whether to include full content or summary
        max_items: Maximum number of items to include

    Returns:
        List of FeedItem objects
    """
    items: list[FeedItem] = []

    for page in pages[:max_items]:
        published = page.published_at

        if not published:
            continue
        modified = page.modified_at or published

        url = f"{site_url}{page.url}"
        content = page.html
        if not content and page.body:
            content = render_markdown(
                page.body,
                page.base_url or "/wiki/",
            )

        summary = extract_summary(content) if not full_content else None

        item = FeedItem(
            title=page.title,
            url=url,
            content=content if full_content else "",
            published=published,
            updated=modified,
            summary=summary,
        )
        items.append(item)

    return items


def _select_feed_pages(pages: list[Page], wiki_prefix: str) -> list[Page]:
    """Select pages eligible for inclusion in the Atom feed."""
    if not wiki_prefix:
        return pages

    wiki_url_prefix = f"/{wiki_prefix}/"
    return [page for page in pages if page.url.startswith(wiki_url_prefix)]


def _remove_stale_feed(output_dir: Path) -> None:
    """Remove a previously generated feed file, if present."""
    feed_file = output_dir / "feed.xml"
    if feed_file.exists():
        feed_file.unlink()


def _create_updates_entry(
    updated_pages: list[Page], site_url: str
) -> dict[str, str] | None:
    """Create template data for the updates digest entry."""
    if not updated_pages:
        return None

    most_recent_update = updated_pages[0].modified_at
    if most_recent_update is None:
        return None

    return {
        "content": generate_updates_digest(updated_pages, site_url),
        "updated": format_atom_date(most_recent_update),
    }


def _get_feed_updated(
    new_items: list[FeedItem], updated_pages: list[Page], now: datetime
) -> datetime:
    """Return the newest timestamp across all feed entries."""
    all_dates = [item.updated for item in new_items]

    if updated_pages:
        latest_update = updated_pages[0].modified_at
        if latest_update is not None:
            all_dates.append(latest_update)

    return max(all_dates, default=now)


def _format_template_items(items: list[FeedItem]) -> list[dict[str, str | None]]:
    """Convert feed items into template-friendly dictionaries."""
    return [
        {
            "title": item.title,
            "url": item.url,
            "published": format_atom_date(item.published),
            "updated": format_atom_date(item.updated),
            "content": item.content,
            "summary": item.summary,
        }
        for item in items
    ]


def generate_feed(
    pages: list[Page],
    config: "Config",
    templates: "Environment",
    output_dir: Path,
) -> None:
    """Generate Atom feed with new pages and updates digest.

    Args:
        pages: List of published Page objects
        config: Site configuration
        templates: Jinja2 environment
        output_dir: Build output directory
    """
    from . import __version__

    feed_config = config.feed
    if not feed_config.enabled:
        return

    site_url = config.site.url.rstrip("/")
    now = datetime.now(timezone.utc)

    wiki_prefix = config.build.wiki_prefix.strip("/")
    feed_pages = _select_feed_pages(pages, wiki_prefix)
    new_pages, updated_pages = classify_pages(feed_pages, feed_config.window, now)

    if not new_pages and not updated_pages:
        _remove_stale_feed(output_dir)
        return

    new_items = create_feed_items(
        new_pages,
        site_url,
        feed_config.full_content,
        feed_config.items,
    )

    updates_entry = _create_updates_entry(updated_pages, site_url)
    feed_title = feed_config.title or config.site.name
    feed_description = feed_config.description or f"{config.site.name} - Recent updates"
    feed_updated = _get_feed_updated(new_items, updated_pages, now)
    formatted_items = _format_template_items(new_items)

    try:
        template = templates.get_template("feed.xml")
    except Exception as e:
        from .logging import warning

        warning(f"Failed to load feed template: {e}")
        warning("Feed generation skipped. Ensure feed.xml template exists.")
        return
    wiki_url = f"{site_url}/{wiki_prefix}/" if wiki_prefix else f"{site_url}/"

    feed_xml = template.render(
        config=config,
        feed_title=feed_title,
        feed_description=feed_description,
        feed_updated=format_atom_date(feed_updated),
        new_items=formatted_items,
        updates_entry=updates_entry,
        full_content=feed_config.full_content,
        version=__version__,
        wiki_url=wiki_url,
    )

    # Write feed file
    (output_dir / "feed.xml").write_text(feed_xml, encoding="utf-8")
