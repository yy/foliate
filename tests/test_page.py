"""Tests for the Page model and frontmatter helpers."""

import os
import tempfile
from datetime import date, datetime, timezone

from foliate.page import Page, _coerce_str, _coerce_tags, parse_frontmatter_date


class TestParseFrontmatterDate:
    """Tests for parse_frontmatter_date."""

    def test_none_returns_none(self):
        assert parse_frontmatter_date(None) is None

    def test_invalid_string_returns_none(self):
        assert parse_frontmatter_date("not-a-date") is None

    def test_non_string_non_date_returns_none(self):
        assert parse_frontmatter_date(12345) is None
        assert parse_frontmatter_date([]) is None

    def test_date_object(self):
        result = parse_frontmatter_date(date(2024, 6, 15))
        assert result == datetime(2024, 6, 15, tzinfo=timezone.utc)

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2024, 6, 15, 12, 30)
        result = parse_frontmatter_date(dt)
        assert result.tzinfo == timezone.utc
        assert result.hour == 12

    def test_aware_datetime_converted_to_utc(self):
        from datetime import timedelta

        tz_kst = timezone(timedelta(hours=9))
        dt = datetime(2024, 6, 15, 18, 0, tzinfo=tz_kst)
        result = parse_frontmatter_date(dt)
        assert result.tzinfo == timezone.utc
        assert result.hour == 9  # 18:00 KST = 09:00 UTC

    def test_iso_date_string(self):
        result = parse_frontmatter_date("2024-03-15")
        assert result == datetime(2024, 3, 15, tzinfo=timezone.utc)

    def test_iso_datetime_string(self):
        result = parse_frontmatter_date("2024-03-15T10:30:00")
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_iso_datetime_with_tz(self):
        result = parse_frontmatter_date("2024-03-15T10:30:00+09:00")
        assert result.hour == 1  # 10:30+09 = 01:30 UTC
        assert result.tzinfo == timezone.utc

    def test_iso_datetime_with_z(self):
        result = parse_frontmatter_date("2024-03-15T10:30:00Z")
        assert result.hour == 10
        assert result.tzinfo == timezone.utc


class TestCoerceTags:
    """Tests for _coerce_tags."""

    def test_list_of_strings(self):
        assert _coerce_tags(["a", "b", "c"]) == ["a", "b", "c"]

    def test_list_with_non_strings(self):
        assert _coerce_tags([1, 2]) == ["1", "2"]

    def test_single_string(self):
        assert _coerce_tags("solo") == ["solo"]

    def test_empty_string(self):
        assert _coerce_tags("") == []

    def test_none(self):
        assert _coerce_tags(None) == []

    def test_non_list_non_string(self):
        assert _coerce_tags(42) == []


class TestCoerceStr:
    """Tests for _coerce_str."""

    def test_string_passthrough(self):
        assert _coerce_str("hello") == "hello"

    def test_none_returns_fallback(self):
        assert _coerce_str(None) == ""
        assert _coerce_str(None, "default") == "default"

    def test_non_string_stringified(self):
        assert _coerce_str(42) == "42"


class TestPageFromMarkdown:
    """Tests for Page.from_markdown class method."""

    def test_basic_construction(self):
        page = Page.from_markdown(
            "Notes/Hello",
            {"title": "Hello World", "published": True},
            "Some content here.",
            render_html=False,
        )
        assert page.path == "Notes/Hello"
        assert page.title == "Hello World"
        assert page.url == "/wiki/Notes/Hello/"
        assert page.base_url == "/wiki/"
        assert page.is_published is True
        assert page.body == "Some content here."

    def test_title_fallback_to_path(self):
        page = Page.from_markdown("MyPath", {}, "body", render_html=False)
        assert page.title == "MyPath"

    def test_empty_title_falls_back_to_path(self):
        page = Page.from_markdown("MyPath", {"title": ""}, "body", render_html=False)
        assert page.title == "MyPath"

    def test_description_from_meta(self):
        page = Page.from_markdown(
            "P", {"description": "A desc"}, "body text", render_html=False
        )
        assert page.description == "A desc"

    def test_description_extracted_from_body(self):
        page = Page.from_markdown("P", {}, "First paragraph.", render_html=False)
        assert page.description == "First paragraph."

    def test_image_from_meta(self):
        page = Page.from_markdown("P", {"image": "photo.png"}, "", render_html=False)
        assert page.image == "/assets/photo.png"

    def test_absolute_image_not_prefixed(self):
        page = Page.from_markdown(
            "P", {"image": "/img/photo.png"}, "", render_html=False
        )
        assert page.image == "/img/photo.png"

    def test_http_image_not_prefixed(self):
        page = Page.from_markdown(
            "P", {"image": "https://example.com/photo.png"}, "", render_html=False
        )
        assert page.image == "https://example.com/photo.png"

    def test_tags_coerced(self):
        page = Page.from_markdown("P", {"tags": ["a", "b"]}, "", render_html=False)
        assert page.tags == ["a", "b"]

    def test_tags_single_string(self):
        page = Page.from_markdown("P", {"tags": "solo"}, "", render_html=False)
        assert page.tags == ["solo"]

    def test_custom_base_url(self):
        page = Page.from_markdown("about", {}, "", render_html=False, base_url="/")
        assert page.url == "/about/"
        assert page.base_url == "/"

    def test_empty_base_url(self):
        page = Page.from_markdown("about", {}, "", render_html=False, base_url="")
        assert page.url == "about/"
        assert page.base_url == ""

    def test_published_at_from_date_string(self):
        page = Page.from_markdown(
            "P", {"published": True, "date": "2024-01-15"}, "", render_html=False
        )
        assert page.published_at == datetime(2024, 1, 15, tzinfo=timezone.utc)

    def test_published_at_from_published_date(self):
        page = Page.from_markdown(
            "P", {"published": "2024-06-01"}, "", render_html=False
        )
        assert page.published_at == datetime(2024, 6, 1, tzinfo=timezone.utc)

    def test_modified_at_from_meta(self):
        page = Page.from_markdown(
            "P", {"modified": "2024-07-01"}, "", render_html=False
        )
        assert page.modified_at == datetime(2024, 7, 1, tzinfo=timezone.utc)

    def test_file_path_sets_mtime(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"content")
            f.flush()
            tmp = f.name
        try:
            from pathlib import Path as P

            page = Page.from_markdown(
                "Test", {}, "content", render_html=False, file_path=P(tmp)
            )
            assert page.file_mtime is not None
            assert page.file_modified is not None
            assert page.published_at is not None
        finally:
            os.unlink(tmp)

    def test_no_file_path_leaves_mtime_none(self):
        page = Page.from_markdown("P", {}, "", render_html=False)
        assert page.file_mtime is None
        assert page.file_modified is None


class TestResolvePublishedAt:
    """Tests for _resolve_published_at static method."""

    def test_published_date_string(self):
        result = Page._resolve_published_at("2024-01-01", None, None)
        assert result == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_published_true_falls_through_to_date(self):
        result = Page._resolve_published_at(True, "2024-06-15", None)
        assert result == datetime(2024, 6, 15, tzinfo=timezone.utc)

    def test_published_false_falls_through_to_date(self):
        result = Page._resolve_published_at(False, "2024-06-15", None)
        assert result == datetime(2024, 6, 15, tzinfo=timezone.utc)

    def test_falls_back_to_file_mtime(self):
        mtime = datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp()
        result = Page._resolve_published_at(None, None, mtime)
        assert result is not None
        assert result.year == 2024

    def test_no_info_returns_none(self):
        assert Page._resolve_published_at(None, None, None) is None


class TestResolveModifiedAt:
    """Tests for _resolve_modified_at static method."""

    def test_explicit_modified(self):
        result = Page._resolve_modified_at("2024-07-01", None, None)
        assert result == datetime(2024, 7, 1, tzinfo=timezone.utc)

    def test_falls_back_to_mtime(self):
        mtime = datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp()
        result = Page._resolve_modified_at(None, mtime, None)
        assert result is not None
        assert result.year == 2024

    def test_falls_back_to_published_at(self):
        pub = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = Page._resolve_modified_at(None, None, pub)
        assert result == pub
