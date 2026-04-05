"""Typed page model and frontmatter normalization helpers."""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .markdown_utils import (
    extract_description,
    extract_first_image,
    render_markdown,
    slugify_path,
)

type Frontmatter = dict[str, object]


def parse_frontmatter_date(value: object) -> datetime | None:
    """Parse supported frontmatter date values into UTC datetimes."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    if not isinstance(value, str):
        return None

    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

        parsed_date = date.fromisoformat(value)
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            tzinfo=timezone.utc,
        )
    except (TypeError, ValueError):
        return None


def _first_parsed_date(*values: object) -> datetime | None:
    """Return the first value that parses as a supported frontmatter date."""
    for value in values:
        parsed = parse_frontmatter_date(value)
        if parsed is not None:
            return parsed
    return None


def _file_mtime_to_utc(file_mtime: float | None) -> datetime | None:
    """Convert a filesystem mtime into a UTC datetime."""
    if file_mtime is None:
        return None
    try:
        return datetime.fromtimestamp(file_mtime, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _resolve_explicit_published_at(
    published: object | None, date_value: object | None
) -> datetime | None:
    """Resolve the first explicit publish date from frontmatter."""
    published_value = (
        published
        if published is not None and published is not True and published is not False
        else None
    )
    return _first_parsed_date(published_value, date_value)


def _resolve_explicit_modified_at(
    updated: object | None, modified: object | None
) -> datetime | None:
    """Resolve the first explicit modified date from frontmatter."""
    return _first_parsed_date(updated, modified)


def _coerce_tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(tag) for tag in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _coerce_str(value: object, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    return fallback


def _build_page_url(page_path: str, base_url: str, slugify_urls: bool) -> str:
    """Build the public URL for a page path."""
    url_path = slugify_path(page_path) if slugify_urls else page_path
    return f"{base_url}{url_path}/"


def _resolve_description(meta: Frontmatter, markdown_content: str) -> str:
    """Resolve description from frontmatter or content."""
    return _coerce_str(meta.get("description")) or extract_description(markdown_content)


def _normalize_image_path(image: str | None) -> str | None:
    """Normalize image references to public asset paths."""
    if not image:
        return None

    normalized = image.strip()
    if normalized.startswith("assets/"):
        return f"/{normalized}"
    if normalized.startswith(("/", "http://", "https://")):
        return normalized
    return f"/assets/{normalized}"


def _resolve_image(meta: Frontmatter, markdown_content: str) -> str | None:
    """Resolve image from frontmatter or first markdown image."""
    image_value = _coerce_str(meta.get("image"))
    return _normalize_image_path(image_value or extract_first_image(markdown_content))


def _resolve_file_metadata(
    file_path: Path | None,
) -> tuple[str | None, float | None]:
    """Read derived file metadata for a source path."""
    if file_path is None:
        return None, None

    file_mtime = file_path.stat().st_mtime
    file_modified = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")
    return file_modified, file_mtime


def _resolve_page_dates(
    meta: Frontmatter, file_mtime: float | None
) -> tuple[datetime | None, datetime | None, str | None, str | None]:
    """Resolve published/modified timestamps and display values."""
    published = meta.get("published")
    date_value = meta.get("date")
    explicit_modified_at = _resolve_explicit_modified_at(
        meta.get("updated"), meta.get("modified")
    )
    published_at = _resolve_explicit_published_at(
        published, date_value
    ) or _file_mtime_to_utc(file_mtime)
    modified_at = (
        explicit_modified_at or _file_mtime_to_utc(file_mtime) or published_at
    )
    updated_display = (
        explicit_modified_at.strftime("%Y-%m-%d") if explicit_modified_at else None
    )
    modified_display = modified_at.strftime("%Y-%m-%d") if modified_at else None
    return published_at, modified_at, modified_display, updated_display


@dataclass
class Page:
    """Normalized build-time page object."""

    path: str
    title: str
    meta: Frontmatter
    body: str
    html: str
    published: object | None
    date: object | None
    url: str
    base_url: str
    description: str
    image: str | None
    tags: list[str] = field(default_factory=list)
    file_modified: str | None = None
    file_mtime: float | None = None
    is_published: bool = False
    published_at: datetime | None = None
    modified_at: datetime | None = None
    modified_display: str | None = None
    updated: str | None = None

    @classmethod
    def from_markdown(
        cls,
        page_path: str,
        meta: Frontmatter,
        markdown_content: str,
        render_html: bool = True,
        file_path: Path | None = None,
        base_url: str = "/wiki/",
        slugify_urls: bool = False,
    ) -> "Page":
        """Create a normalized page object from source markdown."""
        published = meta.get("published")
        page_url = _build_page_url(page_path, base_url, slugify_urls)
        description = _resolve_description(meta, markdown_content)
        image = _resolve_image(meta, markdown_content)
        file_modified, file_mtime = _resolve_file_metadata(file_path)
        published_at, modified_at, modified_display, updated_display = (
            _resolve_page_dates(meta, file_mtime)
        )

        return cls(
            path=page_path,
            title=_coerce_str(meta.get("title"), fallback=page_path) or page_path,
            meta=meta,
            body=markdown_content,
            html=render_markdown(markdown_content, base_url) if render_html else "",
            published=published,
            date=meta.get("date"),
            url=page_url,
            base_url=base_url,
            description=description,
            image=image,
            tags=_coerce_tags(meta.get("tags")),
            file_modified=file_modified,
            file_mtime=file_mtime,
            is_published=bool(published),
            published_at=published_at,
            modified_at=modified_at,
            modified_display=modified_display,
            updated=updated_display,
        )
