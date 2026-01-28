"""Atom feed generation for foliate."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

# Re-export FeedConfig from config for convenience
from .config import FeedConfig

__all__ = ["FeedConfig", "FeedItem", "generate_feed"]


@dataclass
class FeedItem:
    """A single item in a feed."""

    title: str
    url: str
    content: str
    published: datetime
    updated: datetime
    summary: Optional[str] = None


def parse_frontmatter_date(value) -> Optional[datetime]:
    """Parse a frontmatter date value to datetime.

    Accepts:
        - ISO 8601 date string: "2024-03-15"
        - ISO 8601 datetime string: "2024-03-15T10:30:00"
        - With timezone: "2024-03-15T10:30:00+09:00"
        - date object
        - datetime object

    Returns:
        datetime in UTC, or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    if not isinstance(value, str):
        return None

    # Try parsing as ISO date/datetime
    try:
        if "T" in value:
            # Datetime - normalize Z to +00:00 for fromisoformat
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                # No timezone info, assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        else:
            # Date only
            d = date.fromisoformat(value)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def get_published_date(page: dict) -> Optional[datetime]:
    """Extract publication date from page.

    Resolution order:
        1. published field as date (not boolean True)
        2. date field
        3. file modification time (fallback)
    """
    meta = page.get("meta", {})

    # Check published field (if it's a date, not boolean)
    published = meta.get("published")
    if published is not None and published is not True and published is not False:
        result = parse_frontmatter_date(published)
        if result:
            return result

    # Check date field
    date_val = meta.get("date")
    if date_val:
        result = parse_frontmatter_date(date_val)
        if result:
            return result

    # Fallback to file mtime
    file_mtime = page.get("file_mtime")
    if file_mtime:
        try:
            return datetime.fromtimestamp(file_mtime, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass

    return None


def get_modified_date(page: dict) -> Optional[datetime]:
    """Extract modification date from page.

    Resolution order:
        1. modified field in frontmatter
        2. file modification time
        3. published date (fallback)
    """
    meta = page.get("meta", {})

    # Check modified field
    modified = meta.get("modified")
    if modified:
        result = parse_frontmatter_date(modified)
        if result:
            return result

    # Fallback to file mtime
    file_mtime = page.get("file_mtime")
    if file_mtime:
        try:
            return datetime.fromtimestamp(file_mtime, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass

    # Final fallback to published date
    return get_published_date(page)


def format_atom_date(dt: datetime) -> str:
    """Format datetime as RFC 3339 for Atom.

    Args:
        dt: datetime object (should be in UTC)

    Returns:
        RFC 3339 formatted string like "2024-03-15T10:30:00Z"
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_pages(
    pages: list[dict],
    window_days: int,
    now: Optional[datetime] = None,
) -> tuple[list[dict], list[dict]]:
    """Classify pages into 'new' and 'updated' categories.

    Args:
        pages: List of page dictionaries
        window_days: Number of days to look back
        now: Current datetime (for testing), defaults to now

    Returns:
        (new_pages, updated_pages) - both sorted by date descending
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_start = now - timedelta(days=window_days)
    new_pages = []
    updated_pages = []

    for page in pages:
        published = get_published_date(page)
        modified = get_modified_date(page)

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

    # Sort by date descending
    new_pages.sort(key=lambda p: get_published_date(p) or now, reverse=True)
    updated_pages.sort(key=lambda p: get_modified_date(p) or now, reverse=True)

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


def generate_updates_digest(pages: list[dict], site_url: str) -> str:
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
        title = escape(page.get("title", page["path"]))
        url = escape(f"{site_url}{page['url']}", quote=True)
        modified = get_modified_date(page)
        date_str = modified.strftime("%B %d, %Y") if modified else ""

        lines.append(f'  <li><a href="{url}">{title}</a> - {date_str}</li>')

    lines.append("</ul>")
    return "\n".join(lines)


def create_feed_items(
    pages: list[dict],
    site_url: str,
    full_content: bool,
    max_items: int,
) -> list[FeedItem]:
    """Create FeedItem objects from pages.

    Args:
        pages: List of page dictionaries
        site_url: Base URL of the site
        full_content: Whether to include full content or summary
        max_items: Maximum number of items to include

    Returns:
        List of FeedItem objects
    """
    items = []

    for page in pages[:max_items]:
        published = get_published_date(page)
        modified = get_modified_date(page) or published

        if not published:
            continue

        url = f"{site_url}{page['url']}"
        content = page.get("html", "")
        summary = extract_summary(content) if not full_content else None

        item = FeedItem(
            title=page.get("title", page["path"]),
            url=url,
            content=content if full_content else "",
            published=published,
            updated=modified,
            summary=summary,
        )
        items.append(item)

    return items


def generate_feed(
    pages: list[dict],
    config: "Config",
    templates: "Environment",
    output_dir: Path,
) -> None:
    """Generate Atom feed with new pages and updates digest.

    Args:
        pages: List of published page dictionaries
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

    # Filter out homepage content (only include wiki pages)
    wiki_prefix = config.build.wiki_prefix.strip("/")
    wiki_url_prefix = f"/{wiki_prefix}/" if wiki_prefix else "/"

    # Only include pages whose URL starts with wiki prefix
    # This excludes _homepage/ content which goes to /
    wiki_pages = [p for p in pages if p.get("url", "").startswith(wiki_url_prefix)]

    # If wiki prefix is empty, we can't distinguish - include all pages
    # Otherwise, only include wiki pages
    if wiki_prefix:
        feed_pages = wiki_pages
    else:
        feed_pages = pages

    # Classify pages
    new_pages, updated_pages = classify_pages(feed_pages, feed_config.window, now)

    # If no pages in either category, remove stale feed and skip generation
    if not new_pages and not updated_pages:
        feed_file = output_dir / "feed.xml"
        if feed_file.exists():
            feed_file.unlink()
        return

    # Create feed items for new pages
    new_items = create_feed_items(
        new_pages,
        site_url,
        feed_config.full_content,
        feed_config.items,
    )

    # Create updates digest entry if there are updated pages
    updates_entry = None
    if updated_pages:
        digest_content = generate_updates_digest(updated_pages, site_url)
        most_recent_update = get_modified_date(updated_pages[0])
        updates_entry = {
            "content": digest_content,
            "updated": format_atom_date(most_recent_update),
        }

    # Determine feed metadata
    feed_title = feed_config.title or config.site.name
    feed_description = feed_config.description or f"{config.site.name} - Recent updates"

    # Determine feed updated time (most recent of all entries)
    all_dates = []
    if new_items:
        all_dates.extend(item.updated for item in new_items)
    if updates_entry and updated_pages:
        all_dates.append(get_modified_date(updated_pages[0]))
    feed_updated = max(all_dates) if all_dates else now

    # Format items for template
    formatted_items = [
        {
            "title": item.title,
            "url": item.url,
            "published": format_atom_date(item.published),
            "updated": format_atom_date(item.updated),
            "content": item.content,
            "summary": item.summary,
        }
        for item in new_items
    ]

    # Render feed template
    template = templates.get_template("feed.xml")
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
