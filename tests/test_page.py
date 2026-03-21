"""Tests for the typed page model."""

from datetime import date, datetime, timezone

from foliate.page import Page, parse_frontmatter_date


class TestParseFrontmatterDate:
    """Tests for frontmatter date parsing."""

    def test_returns_none_for_missing_or_invalid(self):
        assert parse_frontmatter_date(None) is None
        assert parse_frontmatter_date(123) is None
        assert parse_frontmatter_date("not-a-date") is None

    def test_parses_date_string(self):
        result = parse_frontmatter_date("2024-03-15")

        assert result == datetime(2024, 3, 15, tzinfo=timezone.utc)

    def test_parses_datetime_object(self):
        value = datetime(2024, 3, 15, 10, 30, tzinfo=timezone.utc)

        assert parse_frontmatter_date(value) == value

    def test_parses_date_object(self):
        result = parse_frontmatter_date(date(2024, 3, 15))

        assert result == datetime(2024, 3, 15, tzinfo=timezone.utc)

    def test_normalizes_offset_datetime(self):
        result = parse_frontmatter_date("2024-03-15T10:30:00+09:00")

        assert result == datetime(2024, 3, 15, 1, 30, tzinfo=timezone.utc)


class TestPageFromMarkdown:
    """Tests for page construction and normalization."""

    def test_builds_basic_page(self):
        page = Page.from_markdown(
            "notes/test",
            {"title": "Test Page", "tags": ["alpha", "beta"]},
            "# Hello\n\nA paragraph long enough to become a description.",
            render_html=False,
        )

        assert page.path == "notes/test"
        assert page.title == "Test Page"
        assert page.url == "/wiki/notes/test/"
        assert page.tags == ["alpha", "beta"]
        assert page.description != ""

    def test_falls_back_to_path_for_non_string_title(self):
        page = Page.from_markdown(
            "notes/test",
            {"title": False},
            "Body",
            render_html=False,
        )

        assert page.title == "notes/test"

    def test_non_string_description_and_image_are_treated_as_missing(self):
        page = Page.from_markdown(
            "notes/test",
            {"description": False, "image": False},
            "![alt](image.png)\n\nA paragraph long enough to become a description.",
            render_html=False,
        )

        assert page.description != "False"
        assert page.image == "/assets/image.png"

    def test_normalizes_assets_image_paths_and_ignores_titles(self):
        titled = Page.from_markdown(
            "notes/titled",
            {},
            '![alt](image.png "Title")',
            render_html=False,
        )
        asset_path = Page.from_markdown(
            "notes/asset",
            {},
            "![alt](assets/img.png)",
            render_html=False,
        )

        assert titled.image == "/assets/image.png"
        assert asset_path.image == "/assets/img.png"

    def test_coerces_string_tags_and_ignores_invalid_tag_values(self):
        page = Page.from_markdown(
            "notes/test",
            {"tags": "solo"},
            "Body",
            render_html=False,
        )
        invalid_page = Page.from_markdown(
            "notes/invalid",
            {"tags": 123},
            "Body",
            render_html=False,
        )

        assert page.tags == ["solo"]
        assert invalid_page.tags == []

    def test_resolves_published_and_modified_dates(self):
        page = Page.from_markdown(
            "notes/test",
            {
                "published": "2024-03-15",
                "modified": "2024-03-20",
            },
            "Body",
            render_html=False,
        )

        assert page.is_published is True
        assert page.published_at == datetime(2024, 3, 15, tzinfo=timezone.utc)
        assert page.modified_at == datetime(2024, 3, 20, tzinfo=timezone.utc)

    def test_populates_file_times_from_file_path(self, tmp_path):
        md_file = tmp_path / "page.md"
        md_file.write_text("Body")

        page = Page.from_markdown(
            "notes/test",
            {},
            "Body",
            render_html=False,
            file_path=md_file,
        )

        assert page.file_mtime is not None
        assert page.file_modified is not None
