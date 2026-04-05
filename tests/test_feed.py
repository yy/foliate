"""Tests for Atom feed generation."""

from datetime import datetime, timedelta, timezone

from foliate.config import FeedConfig
from foliate.feed import (
    FeedItem,
    classify_pages,
    extract_summary,
    format_atom_date,
    generate_updates_digest,
)
from foliate.page import Page


def make_page(
    path: str,
    *,
    title: str | None = None,
    url: str | None = None,
    html: str = "",
    body: str = "",
    base_url: str = "/wiki/",
    published_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Page:
    """Build a Page with explicit timestamps for feed-focused tests."""
    resolved_title = title or path
    resolved_url = url or f"{base_url}{path}/"
    resolved_modified_at = modified_at or published_at
    updated_display = None
    if modified_at is not None and modified_at != published_at:
        updated_display = modified_at.strftime("%Y-%m-%d")

    return Page(
        path=path,
        title=resolved_title,
        meta={},
        body=body,
        html=html,
        published=published_at is not None,
        date=None,
        url=resolved_url,
        base_url=base_url,
        description="",
        image=None,
        tags=[],
        file_modified=None,
        file_mtime=None,
        is_published=published_at is not None,
        published_at=published_at,
        modified_at=resolved_modified_at,
        updated=updated_display,
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
        recent_published = now - timedelta(days=5)

        pages = [make_page("NewPage", published_at=recent_published)]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 1
        assert len(updated_pages) == 0
        assert new_pages[0].path == "NewPage"

    def test_updated_page(self):
        """Page with old publish date and recent modification becomes updated."""
        now = datetime.now(timezone.utc)
        old_published = now - timedelta(days=60)
        recent_modified = now - timedelta(days=5)

        pages = [
            make_page(
                "UpdatedPage",
                published_at=old_published,
                modified_at=recent_modified,
            )
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 0
        assert len(updated_pages) == 1
        assert updated_pages[0].path == "UpdatedPage"

    def test_page_outside_window(self):
        """Page with all dates older than window is excluded."""
        now = datetime.now(timezone.utc)
        old_timestamp = now - timedelta(days=60)

        pages = [
            make_page(
                "OldPage",
                published_at=old_timestamp,
                modified_at=old_timestamp,
            )
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 0
        assert len(updated_pages) == 0

    def test_new_page_with_modification(self):
        """Page new and modified still counts as new."""
        now = datetime.now(timezone.utc)
        recent_published = now - timedelta(days=5)
        more_recent_modified = now - timedelta(days=2)

        pages = [
            make_page(
                "NewAndModified",
                published_at=recent_published,
                modified_at=more_recent_modified,
            )
        ]

        new_pages, updated_pages = classify_pages(pages, window_days=30, now=now)

        assert len(new_pages) == 1
        assert len(updated_pages) == 0

    def test_pages_sorted_by_date_descending(self):
        """Pages are sorted by date, most recent first."""
        now = datetime.now(timezone.utc)
        date1 = now - timedelta(days=10)
        date2 = now - timedelta(days=5)
        date3 = now - timedelta(days=2)

        pages = [
            make_page("Page1", published_at=date1),
            make_page("Page2", published_at=date2),
            make_page("Page3", published_at=date3),
        ]

        new_pages, _ = classify_pages(pages, window_days=30, now=now)

        assert [p.path for p in new_pages] == ["Page3", "Page2", "Page1"]

    def test_pages_with_same_date_sorted_by_path(self):
        """Pages with the same date are sorted deterministically by path."""
        now = datetime.now(timezone.utc)
        same_date = now - timedelta(days=5)

        # Create pages with same date but different paths
        # Input order intentionally scrambled
        pages = [
            make_page("Zebra", published_at=same_date),
            make_page("Alpha", published_at=same_date),
            make_page("Middle", published_at=same_date),
        ]

        new_pages, _ = classify_pages(pages, window_days=30, now=now)

        # Should be sorted alphabetically by path as secondary sort
        assert [p.path for p in new_pages] == ["Alpha", "Middle", "Zebra"]

    def test_updated_pages_with_same_date_sorted_by_path(self):
        """Updated pages with the same modification date are sorted by path."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=60)
        same_mtime = now - timedelta(days=5)

        # Create pages with same modification time but different paths
        pages = [
            make_page("Zebra", published_at=old_date, modified_at=same_mtime),
            make_page("Alpha", published_at=old_date, modified_at=same_mtime),
            make_page("Middle", published_at=old_date, modified_at=same_mtime),
        ]

        _, updated_pages = classify_pages(pages, window_days=30, now=now)

        # Should be sorted alphabetically by path as secondary sort
        assert [p.path for p in updated_pages] == ["Alpha", "Middle", "Zebra"]


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
        recent_modified = now - timedelta(days=2)

        pages = [
            make_page(
                "PageA",
                title="Page A Title",
                url="/wiki/PageA/",
                modified_at=recent_modified,
            ),
            make_page(
                "PageB",
                title="Page B Title",
                url="/wiki/PageB/",
                modified_at=recent_modified,
            ),
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
            make_page(
                "TestPage",
                title="Test Page",
                url="/wiki/TestPage/",
                modified_at=datetime(2024, 3, 15, tzinfo=timezone.utc),
            ),
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "TestPage",
                title="Test Page Title",
                url="/wiki/TestPage/",
                html="<p>Full content here</p>",
                published_at=recent_published,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "TestPage",
                title="Test Page Title",
                url="/wiki/TestPage/",
                html="<p>This is a summary paragraph.</p><p>Second paragraph.</p>",
                published_at=recent_published,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                f"Page{i}",
                title=f"Page {i}",
                url=f"/wiki/Page{i}/",
                published_at=recent_published,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "CachedPage",
                title="Cached Page",
                url="/wiki/CachedPage/",
                body="# Heading\n\nRendered body text.",
                base_url="/wiki/",
                published_at=recent_published,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "TestPage",
                title="Test Page",
                url="/wiki/TestPage/",
                html="<p>Content</p>",
                published_at=recent_published,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "TestPage",
                title="Test Page",
                url="/wiki/TestPage/",
                html="<p>Content</p>",
                published_at=recent_published,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "about",
                title="About Page",
                url="/about/",
                html="<p>About content</p>",
                published_at=recent_published,
            ),
            make_page(
                "WikiPage",
                title="Wiki Page",
                url="/wiki/WikiPage/",
                html="<p>Wiki content</p>",
                published_at=recent_published,
            ),
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
        old_published = now - timedelta(days=60)
        recent_modified = now - timedelta(days=5)

        pages = [
            make_page(
                "UpdatedPage",
                title="Updated Page",
                url="/wiki/UpdatedPage/",
                html="<p>Updated content</p>",
                published_at=old_published,
                modified_at=recent_modified,
            )
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "TestPage",
                title="Test Page",
                url="/wiki/TestPage/",
                html="<p>Content with <strong>markup</strong></p>",
                published_at=recent_published,
            )
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
        old_timestamp = now - timedelta(days=60)

        # All pages are outside the window
        pages = [
            make_page(
                "OldPage",
                title="Old Page",
                url="/wiki/OldPage/",
                html="<p>Old content</p>",
                published_at=old_timestamp,
                modified_at=old_timestamp,
            )
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
        recent_published = now - timedelta(days=5)

        # Mix of pages that would normally be homepage vs wiki content
        # With empty prefix, all should be included
        pages = [
            make_page(
                "about",
                title="About Page",
                url="/about/",
                html="<p>About content</p>",
                published_at=recent_published,
            ),
            make_page(
                "notes/MyNote",
                title="My Note",
                url="/notes/MyNote/",
                html="<p>Note content</p>",
                published_at=recent_published,
            ),
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
        recent_published = now - timedelta(days=5)

        pages = [
            make_page(
                "TestPage",
                title="Test Page",
                url="/wiki/TestPage/",
                html="<p>Content</p>",
                published_at=recent_published,
            )
        ]

        generate_feed(pages, config, env, build_dir)

        # Feed file should not exist
        feed_file = build_dir / "feed.xml"
        assert not feed_file.exists()

        # Warning messages should be output to stderr
        captured = capsys.readouterr()
        assert "Failed to load feed template" in captured.err
        assert "Feed generation skipped" in captured.err
