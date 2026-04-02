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
        url_path = slugify_path(page_path) if slugify_urls else page_path
        page_url = f"{base_url}{url_path}/"

        description = _coerce_str(meta.get("description")) or extract_description(
            markdown_content
        )

        image_value = _coerce_str(meta.get("image"))
        image = image_value or extract_first_image(markdown_content)
        if image:
            image = image.strip()
            if image.startswith("assets/"):
                image = f"/{image}"
            elif not image.startswith(("/", "http://", "https://")):
                image = f"/assets/{image}"

        file_modified: str | None = None
        file_mtime: float | None = None
        if file_path:
            file_mtime = file_path.stat().st_mtime
            file_modified = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")

        published = meta.get("published")
        date_value = meta.get("date")
        updated_value = meta.get("updated")
        modified_value = meta.get("modified")
        published_at = cls._resolve_published_at(published, date_value, file_mtime)
        modified_at = cls._resolve_modified_at(
            updated_value, modified_value, file_mtime, published_at
        )

        explicit = parse_frontmatter_date(updated_value) or parse_frontmatter_date(
            modified_value
        )
        updated_display = explicit.strftime("%Y-%m-%d") if explicit else None

        return cls(
            path=page_path,
            title=_coerce_str(meta.get("title"), fallback=page_path) or page_path,
            meta=meta,
            body=markdown_content,
            html=render_markdown(markdown_content, base_url) if render_html else "",
            published=published,
            date=date_value,
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
            updated=updated_display,
        )

    @staticmethod
    def _resolve_published_at(
        published: object | None,
        date_value: object | None,
        file_mtime: float | None,
    ) -> datetime | None:
        if published is not None and published is not True and published is not False:
            parsed = parse_frontmatter_date(published)
            if parsed is not None:
                return parsed

        parsed = parse_frontmatter_date(date_value)
        if parsed is not None:
            return parsed

        if file_mtime is not None:
            try:
                return datetime.fromtimestamp(file_mtime, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None
        return None

    @staticmethod
    def _resolve_modified_at(
        updated: object | None,
        modified: object | None,
        file_mtime: float | None,
        published_at: datetime | None,
    ) -> datetime | None:
        parsed = parse_frontmatter_date(updated)
        if parsed is not None:
            return parsed

        parsed = parse_frontmatter_date(modified)
        if parsed is not None:
            return parsed

        if file_mtime is not None:
            try:
                return datetime.fromtimestamp(file_mtime, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return published_at

        return published_at
