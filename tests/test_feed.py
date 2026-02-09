"""Tests for Atom feed generation."""

from datetime import datetime, timedelta, timezone

from foliate.config import FeedConfig
from foliate.feed import (
    FeedItem,
    classify_pages,
    extract_summary,
    format_atom_date,
    generate_updates_digest,
    get_modified_date,
    get_published_date,
    parse_frontmatter_date,
)


class TestFeedConfig:
    """Tests for FeedConfig dataclass."""

    def test_default_values(self):
        """FeedConfig has sensible defaults."""
        config = FeedConfig()

        assert config.enabled is True
        assert config.title == ""
        assert config.description == ""
        assert config.language == "en"
        assert config.items == 20
        assert config.full_content is True
        assert config.window == 30

    def test_custom_values(self):
        """FeedConfig accepts custom values."""
        config = FeedConfig(
            enabled=False,
            title="Custom Feed",
            description="A custom description",
            language="ko",
            items=10,
            full_content=False,
            window=7,
        )

        assert config.enabled is False
        assert config.title == "Custom Feed"
        assert config.description == "A custom description"
        assert config.language == "ko"
        assert config.items == 10
        assert config.full_content is False
        assert config.window == 7


class TestFeedItem:
    """Tests for FeedItem dataclass."""

    def test_create_item(self):
        """FeedItem can be created with required fields."""
        now = datetime.now(timezone.utc)
        item = FeedItem(
            title="Test Article",
            url="https://example.com/wiki/Test/",
            content="<p>Test content</p>",
            published=now,
            updated=now,
        )

        assert item.title == "Test Article"
        assert item.url == "https://example.com/wiki/Test/"
        assert item.content == "<p>Test content</p>"
        assert item.summary is None

    def test_create_item_with_summary(self):
        """FeedItem can have optional summary."""
        now = datetime.now(timezone.utc)
        item = FeedItem(
            title="Test Article",
            url="https://example.com/wiki/Test/",
            content="<p>Test content</p>",
            published=now,
            updated=now,
            summary="A brief summary",
        )

        assert item.summary == "A brief summary"


class TestParseFrontmatterDate:
    """Tests for parse_frontmatter_date function."""

    def test_parse_date_only(self):
        """Parses ISO date string."""
        result = parse_frontmatter_date("2024-03-15")

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 0
        assert result.tzinfo == timezone.utc

    def test_parse_datetime(self):
        """Parses ISO datetime string."""
        result = parse_frontmatter_date("2024-03-15T10:30:00")

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_datetime_with_positive_timezone(self):
        """Parses datetime with positive timezone offset."""
        result = parse_frontmatter_date("2024-03-15T10:30:00+09:00")

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        # 10:30 +09:00 = 01:30 UTC
        assert result.hour == 1
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_parse_datetime_with_negative_timezone(self):
        """Parses datetime with negative timezone offset."""
        result = parse_frontmatter_date("2024-03-15T10:30:00-05:00")

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        # 10:30 -05:00 = 15:30 UTC
        assert result.hour == 15
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_parse_datetime_with_z_suffix(self):
        """Parses datetime with Z suffix (UTC indicator)."""
        result = parse_frontmatter_date("2024-03-15T10:30:00Z")

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        assert result.tzinfo == timezone.utc

    def test_parse_date_object(self):
        """Handles date object input."""
        from datetime import date

        input_date = date(2024, 3, 15)
        result = parse_frontmatter_date(input_date)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_parse_datetime_object(self):
        """Handles datetime object input."""
        input_dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = parse_frontmatter_date(input_dt)

        assert result == input_dt

    def test_parse_invalid_returns_none(self):
        """Returns None for invalid input."""
        assert parse_frontmatter_date(None) is None
        assert parse_frontmatter_date("invalid") is None
        assert parse_frontmatter_date(123) is None


class TestGetPublishedDate:
    """Tests for get_published_date function."""

    def test_explicit_published_date(self):
        """Uses explicit published date field."""
        page = {"meta": {"published": "2024-03-15"}}
        result = get_published_date(page)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_date_field_fallback(self):
        """Falls back to date field if published is boolean."""
        page = {"meta": {"published": True, "date": "2024-03-10"}}
        result = get_published_date(page)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 10

    def test_file_mtime_fallback(self):
        """Falls back to file modification time."""
        page = {"meta": {}, "file_mtime": 1710460800.0}  # 2024-03-15 00:00:00 UTC
        result = get_published_date(page)

        assert result is not None
        assert result.year == 2024

    def test_returns_none_when_no_date(self):
        """Returns None if no date available."""
        page = {"meta": {}}
        result = get_published_date(page)

        assert result is None

    def test_published_true_without_date_returns_none(self):
        """Page with published: true but no date field returns None."""
        page = {"meta": {"published": True}}
        result = get_published_date(page)

        # published: true alone is not sufficient - needs a resolvable date
        assert result is None


class TestGetModifiedDate:
    """Tests for get_modified_date function."""

    def test_explicit_modified_field(self):
        """Uses explicit modified field."""
        page = {"meta": {"modified": "2024-03-20"}, "file_mtime": 1710460800.0}
        result = get_modified_date(page)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 20

    def test_file_mtime_fallback(self):
        """Falls back to file modification time."""
        page = {"meta": {}, "file_mtime": 1710460800.0}  # 2024-03-15 00:00:00 UTC
        result = get_modified_date(page)

        assert result is not None
        assert result.year == 2024

    def test_returns_published_if_no_modified(self):
        """Falls back to published date if no modified date."""
        page = {"meta": {"published": "2024-03-15"}}
        result = get_modified_date(page)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15


class TestFormatAtomDate:
    """Tests for format_atom_date function."""

    def test_format_utc_datetime(self):
        """Formats UTC datetime as RFC 3339."""
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_atom_date(dt)

        assert result == "2024-03-15T10:30:00Z"

    def test_format_midnight(self):
        """Formats midnight correctly."""
        dt = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        result = format_atom_date(dt)

        assert result == "2024-03-15T00:00:00Z"


class TestClassifyPages:
    """Tests for classify_pages function."""

    def test_new_page_within_window(self):
        """Page published within window is classified as new."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "NewPage",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 1
        assert len(updated_pages) == 0
        assert new_pages[0]["path"] == "NewPage"

    def test_updated_page(self):
        """Page with old publish date but recent modification is classified as updated."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        recent_mtime = (now - timedelta(days=5)).timestamp()

        pages = [
            {
                "path": "UpdatedPage",
                "meta": {"published": old_date},
                "file_mtime": recent_mtime,
            }
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 0
        assert len(updated_pages) == 1
        assert updated_pages[0]["path"] == "UpdatedPage"

    def test_page_outside_window(self):
        """Page with all dates older than window is excluded."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        old_mtime = (now - timedelta(days=60)).timestamp()

        pages = [
            {
                "path": "OldPage",
                "meta": {"published": old_date},
                "file_mtime": old_mtime,
            }
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 0
        assert len(updated_pages) == 0

    def test_new_page_with_modification(self):
        """Page new and modified still counts as new."""
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
        more_recent_mtime = (now - timedelta(days=2)).timestamp()

        pages = [
            {
                "path": "NewAndModified",
                "meta": {"published": recent_date},
                "file_mtime": more_recent_mtime,
            }
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 1
        assert len(updated_pages) == 0

    def test_pages_sorted_by_date_descending(self):
        """Pages are sorted by date, most recent first."""
        now = datetime.now(timezone.utc)
        date1 = (now - timedelta(days=10)).strftime("%Y-%m-%d")
        date2 = (now - timedelta(days=5)).strftime("%Y-%m-%d")
        date3 = (now - timedelta(days=2)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "Page1",
                "meta": {"published": date1},
                "file_mtime": now.timestamp(),
            },
            {
                "path": "Page2",
                "meta": {"published": date2},
                "file_mtime": now.timestamp(),
            },
            {
                "path": "Page3",
                "meta": {"published": date3},
                "file_mtime": now.timestamp(),
            },
        ]

        new_pages, _ = classify_pages(pages, window_days=30, now=now)

        assert [p["path"] for p in new_pages] == ["Page3", "Page2", "Page1"]

    def test_pages_with_same_date_sorted_by_path(self):
        """Pages with the same date are sorted deterministically by path."""
        now = datetime.now(timezone.utc)
        same_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        # Create pages with same date but different paths
        # Input order intentionally scrambled
        pages = [
            {
                "path": "Zebra",
                "meta": {"published": same_date},
                "file_mtime": now.timestamp(),
            },
            {
                "path": "Alpha",
                "meta": {"published": same_date},
                "file_mtime": now.timestamp(),
            },
            {
                "path": "Middle",
                "meta": {"published": same_date},
                "file_mtime": now.timestamp(),
            },
        ]

        new_pages, _ = classify_pages(pages, window_days=30, now=now)

        # Should be sorted alphabetically by path as secondary sort
        assert [p["path"] for p in new_pages] == ["Alpha", "Middle", "Zebra"]

    def test_updated_pages_with_same_date_sorted_by_path(self):
        """Updated pages with the same modification date are sorted by path."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        same_mtime = (now - timedelta(days=5)).timestamp()

        # Create pages with same modification time but different paths
        pages = [
            {
                "path": "Zebra",
                "meta": {"published": old_date},
                "file_mtime": same_mtime,
            },
            {
                "path": "Alpha",
                "meta": {"published": old_date},
                "file_mtime": same_mtime,
            },
            {
                "path": "Middle",
                "meta": {"published": old_date},
                "file_mtime": same_mtime,
            },
        ]

        _, updated_pages = classify_pages(pages, window_days=30, now=now)

        # Should be sorted alphabetically by path as secondary sort
        assert [p["path"] for p in updated_pages] == ["Alpha", "Middle", "Zebra"]


class TestExtractSummary:
    """Tests for extract_summary function."""

    def test_extract_first_paragraph(self):
        """Extracts first paragraph as summary."""
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        result = extract_summary(html)

        assert result == "First paragraph."

    def test_truncates_long_text(self):
        """Truncates text longer than 300 characters."""
        long_text = "A" * 400
        html = f"<p>{long_text}</p>"
        result = extract_summary(html)

        assert len(result) <= 303  # 300 + "..."
        assert result.endswith("...")

    def test_handles_empty_html(self):
        """Handles empty HTML."""
        result = extract_summary("")

        assert result == ""

    def test_strips_tags(self):
        """Strips HTML tags from summary."""
        html = "<p>Text with <strong>bold</strong> and <a href='#'>links</a>.</p>"
        result = extract_summary(html)

        assert "<" not in result
        assert ">" not in result


class TestGenerateUpdatesDigest:
    """Tests for generate_updates_digest function."""

    def test_generates_html_list(self):
        """Generates HTML list of updated pages."""
        now = datetime.now(timezone.utc)
        recent_mtime = (now - timedelta(days=2)).timestamp()

        pages = [
            {
                "path": "PageA",
                "title": "Page A Title",
                "url": "/wiki/PageA/",
                "file_mtime": recent_mtime,
            },
            {
                "path": "PageB",
                "title": "Page B Title",
                "url": "/wiki/PageB/",
                "file_mtime": recent_mtime,
            },
        ]

        result = generate_updates_digest(pages, "https://example.com")

        assert "<ul>" in result
        assert "Page A Title" in result
        assert "Page B Title" in result
        assert "https://example.com/wiki/PageA/" in result

    def test_empty_list(self):
        """Returns empty string for empty list."""
        result = generate_updates_digest([], "https://example.com")

        assert result == ""

    def test_uses_iso_date_format(self):
        """Uses ISO format (YYYY-MM-DD) for language-neutral dates."""
        pages = [
            {
                "path": "TestPage",
                "title": "Test Page",
                "url": "/wiki/TestPage/",
                "meta": {"modified": "2024-03-15"},
            },
        ]

        result = generate_updates_digest(pages, "https://example.com")

        # Should contain ISO date format, not English month names
        assert "2024-03-15" in result
        # Should NOT contain English month names
        assert "March" not in result


class TestCreateFeedItems:
    """Tests for create_feed_items function."""

    def test_creates_items_with_full_content(self):
        """Creates items with full HTML content."""
        from foliate.feed import create_feed_items

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "TestPage",
                "title": "Test Page Title",
                "url": "/wiki/TestPage/",
                "html": "<p>Full content here</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        items = create_feed_items(
            pages, "https://example.com", full_content=True, max_items=10
        )

        assert len(items) == 1
        assert items[0].title == "Test Page Title"
        assert items[0].url == "https://example.com/wiki/TestPage/"
        assert items[0].content == "<p>Full content here</p>"
        assert items[0].summary is None

    def test_creates_items_with_summary(self):
        """Creates items with summary instead of full content."""
        from foliate.feed import create_feed_items

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "TestPage",
                "title": "Test Page Title",
                "url": "/wiki/TestPage/",
                "html": "<p>This is a summary paragraph.</p><p>Second paragraph.</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        items = create_feed_items(
            pages, "https://example.com", full_content=False, max_items=10
        )

        assert len(items) == 1
        assert items[0].summary == "This is a summary paragraph."
        assert items[0].content == ""

    def test_respects_max_items(self):
        """Respects max_items limit."""
        from foliate.feed import create_feed_items

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": f"Page{i}",
                "title": f"Page {i}",
                "url": f"/wiki/Page{i}/",
                "html": "",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
            for i in range(10)
        ]

        items = create_feed_items(
            pages, "https://example.com", full_content=True, max_items=3
        )

        assert len(items) == 3

    def test_renders_content_from_body_when_html_missing(self):
        """Falls back to markdown body rendering for cached pages."""
        from foliate.feed import create_feed_items

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "CachedPage",
                "title": "Cached Page",
                "url": "/wiki/CachedPage/",
                "html": "",
                "body": "# Heading\n\nRendered body text.",
                "base_url": "/wiki/",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        items = create_feed_items(
            pages, "https://example.com", full_content=True, max_items=10
        )

        assert len(items) == 1
        assert "Rendered body text." in items[0].content
        assert "<h1" in items[0].content


class TestGenerateFeed:
    """Integration tests for generate_feed function."""

    def test_generates_feed_xml(self, tmp_path):
        """Generates valid feed.xml file."""
        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        # Setup config
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"
author = "Test Author"

[feed]
enabled = true
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "TestPage",
                "title": "Test Page",
                "url": "/wiki/TestPage/",
                "html": "<p>Content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        generate_feed(pages, config, env, build_dir)

        feed_file = build_dir / "feed.xml"
        assert feed_file.exists()

        content = feed_file.read_text()
        assert '<?xml version="1.0"' in content
        assert "<feed" in content
        assert "Test Site" in content
        assert "Test Page" in content

    def test_skips_when_disabled(self, tmp_path):
        """Skips feed generation when disabled."""
        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"

[feed]
enabled = false
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "TestPage",
                "title": "Test Page",
                "url": "/wiki/TestPage/",
                "html": "<p>Content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        generate_feed(pages, config, env, build_dir)

        feed_file = build_dir / "feed.xml"
        assert not feed_file.exists()

    def test_excludes_homepage_content(self, tmp_path):
        """Excludes homepage content from feed."""
        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"

[feed]
enabled = true
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "about",
                "title": "About Page",
                "url": "/about/",  # Homepage content
                "html": "<p>About content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            },
            {
                "path": "WikiPage",
                "title": "Wiki Page",
                "url": "/wiki/WikiPage/",  # Wiki content
                "html": "<p>Wiki content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            },
        ]

        generate_feed(pages, config, env, build_dir)

        feed_file = build_dir / "feed.xml"
        assert feed_file.exists()

        content = feed_file.read_text()
        assert "Wiki Page" in content
        assert "About Page" not in content

    def test_includes_updates_digest(self, tmp_path):
        """Includes updates digest for modified pages."""
        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"

[feed]
enabled = true
window = 30
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        recent_mtime = (now - timedelta(days=5)).timestamp()

        pages = [
            {
                "path": "UpdatedPage",
                "title": "Updated Page",
                "url": "/wiki/UpdatedPage/",
                "html": "<p>Updated content</p>",
                "meta": {"published": old_date},  # Old publish date
                "file_mtime": recent_mtime,  # Recent modification
            }
        ]

        generate_feed(pages, config, env, build_dir)

        feed_file = build_dir / "feed.xml"
        assert feed_file.exists()

        content = feed_file.read_text()
        assert "Recently Updated Pages" in content
        assert "Updated Page" in content

    def test_generates_valid_xml(self, tmp_path):
        """Generated feed is valid XML."""
        import xml.etree.ElementTree as ET

        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"
author = "Test Author"

[feed]
enabled = true
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "TestPage",
                "title": "Test Page",
                "url": "/wiki/TestPage/",
                "html": "<p>Content with <strong>markup</strong></p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        generate_feed(pages, config, env, build_dir)

        feed_file = build_dir / "feed.xml"
        content = feed_file.read_text()

        # This will raise if XML is malformed
        ET.fromstring(content)

    def test_removes_stale_feed_when_no_pages(self, tmp_path):
        """Removes stale feed.xml when no pages are in window."""
        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"

[feed]
enabled = true
window = 30
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        # Create a stale feed.xml
        stale_feed = build_dir / "feed.xml"
        stale_feed.write_text("<feed>stale content</feed>")
        assert stale_feed.exists()

        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        old_mtime = (now - timedelta(days=60)).timestamp()

        # All pages are outside the window
        pages = [
            {
                "path": "OldPage",
                "title": "Old Page",
                "url": "/wiki/OldPage/",
                "html": "<p>Old content</p>",
                "meta": {"published": old_date},
                "file_mtime": old_mtime,
            }
        ]

        generate_feed(pages, config, env, build_dir)

        # Stale feed should be removed
        assert not stale_feed.exists()

    def test_empty_wiki_prefix_includes_all_pages(self, tmp_path):
        """When wiki_prefix is empty, all pages are included in feed."""
        from jinja2 import Environment

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.templates import get_template_loader

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"

[build]
wiki_prefix = ""

[feed]
enabled = true
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        env = Environment(loader=get_template_loader(tmp_path))

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        # Mix of pages that would normally be homepage vs wiki content
        # With empty prefix, all should be included
        pages = [
            {
                "path": "about",
                "title": "About Page",
                "url": "/about/",  # Would be homepage content with prefix
                "html": "<p>About content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            },
            {
                "path": "notes/MyNote",
                "title": "My Note",
                "url": "/notes/MyNote/",  # Regular content at root
                "html": "<p>Note content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            },
        ]

        generate_feed(pages, config, env, build_dir)

        feed_file = build_dir / "feed.xml"
        assert feed_file.exists()

        content = feed_file.read_text()
        # Both pages should be included when wiki_prefix is empty
        assert "About Page" in content
        assert "My Note" in content

    def test_warns_when_template_fails_to_load(self, tmp_path, capsys):
        """Logs warning when feed template cannot be loaded."""
        from jinja2 import Environment, FileSystemLoader

        from foliate.config import Config
        from foliate.feed import generate_feed
        from foliate.logging import setup_logging

        # Initialize logging to ensure warnings go to stderr
        setup_logging(verbose=False)

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://example.com"

[feed]
enabled = true
"""
        )

        config = Config.load(config_path)
        build_dir = tmp_path / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        # Create a Jinja2 environment with an empty template directory
        # This will cause template loading to fail
        empty_templates_dir = tmp_path / "empty_templates"
        empty_templates_dir.mkdir()
        env = Environment(loader=FileSystemLoader(str(empty_templates_dir)))

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        pages = [
            {
                "path": "TestPage",
                "title": "Test Page",
                "url": "/wiki/TestPage/",
                "html": "<p>Content</p>",
                "meta": {"published": recent},
                "file_mtime": now.timestamp(),
            }
        ]

        generate_feed(pages, config, env, build_dir)

        # Feed file should not exist
        feed_file = build_dir / "feed.xml"
        assert not feed_file.exists()

        # Warning messages should be output to stderr
        captured = capsys.readouterr()
        assert "Failed to load feed template" in captured.err
        assert "Feed generation skipped" in captured.err
