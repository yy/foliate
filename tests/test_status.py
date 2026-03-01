"""Tests for foliate status module."""

from foliate.config import Config
from foliate.status import (
    PageStatus,
    StatusReport,
    format_status_report,
    scan_status,
)


def _make_vault(tmp_path, pages: dict[str, dict]) -> Config:
    """Create a vault with pages and return a Config.

    Args:
        tmp_path: pytest tmp_path fixture
        pages: dict mapping relative file paths (e.g. "test.md") to dicts
               with keys: content (str), and optionally a subdir like "_homepage/about.md"
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    foliate_dir = vault_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text(
        """
[site]
name = "Test Site"
url = "https://test.com"

[build]
home_redirect = "about"
"""
    )

    for rel_path, info in pages.items():
        md_file = vault_path / rel_path
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text(info["content"])

    return Config.load(config_path)


class TestScanStatus:
    """Tests for scan_status()."""

    def test_empty_vault(self, tmp_path):
        """Empty vault returns empty report."""
        config = _make_vault(tmp_path, {})
        report = scan_status(config)
        assert len(report.pages) == 0

    def test_private_page(self, tmp_path):
        """Page without public: true is private."""
        config = _make_vault(
            tmp_path,
            {
                "note.md": {
                    "content": "---\ntitle: Note\n---\nPrivate note.\n",
                },
            },
        )
        report = scan_status(config)
        assert len(report.pages) == 1
        assert report.pages[0].public is False
        assert len(report.private_pages) == 1

    def test_public_page_is_new_before_build(self, tmp_path):
        """Public page shows as 'new' when no build output exists."""
        config = _make_vault(
            tmp_path,
            {
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
        )
        report = scan_status(config)
        assert len(report.public_pages) == 1
        assert report.public_pages[0].state == "new"
        assert len(report.new_pages) == 1

    def test_published_page_detected(self, tmp_path):
        """Published pages are reported correctly."""
        config = _make_vault(
            tmp_path,
            {
                "blog.md": {
                    "content": "---\ntitle: Blog\npublic: true\npublished: true\n---\nPost.\n",
                },
            },
        )
        report = scan_status(config)
        assert len(report.published_pages) == 1
        assert report.published_pages[0].published is True

    def test_homepage_content(self, tmp_path):
        """Homepage content is identified correctly."""
        config = _make_vault(
            tmp_path,
            {
                "_homepage/about.md": {
                    "content": "---\ntitle: About\npublic: true\n---\nAbout page.\n",
                },
            },
        )
        report = scan_status(config)
        assert len(report.pages) == 1
        p = report.pages[0]
        assert p.is_homepage_content is True
        assert p.base_url == "/"
        assert p.page_path == "about"

    def test_unchanged_after_build(self, tmp_path):
        """Page shows as 'unchanged' after a successful build."""
        from foliate.build import build

        config = _make_vault(
            tmp_path,
            {
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
        )
        build(config=config, force_rebuild=True)

        report = scan_status(config)
        assert len(report.public_pages) == 1
        assert report.public_pages[0].state == "unchanged"
        assert len(report.unchanged_pages) == 1

    def test_modified_after_edit(self, tmp_path):
        """Page shows as 'modified' when source is newer than cache."""
        import os
        import time

        from foliate.build import build

        config = _make_vault(
            tmp_path,
            {
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
        )
        build(config=config, force_rebuild=True)

        # Edit the file and set mtime clearly in the future
        md_file = config.vault_path / "test.md"
        md_file.write_text("---\ntitle: Test\npublic: true\n---\nUpdated.\n")
        future = time.time() + 2
        os.utime(md_file, (future, future))

        report = scan_status(config)
        assert len(report.modified_pages) == 1
        assert report.modified_pages[0].state == "modified"

    def test_ignored_folders_excluded(self, tmp_path):
        """Pages in ignored folders are not included."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test"

[build]
ignored_folders = ["_private"]
home_redirect = "about"
"""
        )

        private_dir = vault_path / "_private"
        private_dir.mkdir()
        (private_dir / "secret.md").write_text(
            "---\ntitle: Secret\npublic: true\n---\nSecret.\n"
        )

        config = Config.load(config_path)
        report = scan_status(config)
        assert len(report.pages) == 0

    def test_mixed_pages(self, tmp_path):
        """Mix of public, published, and private pages."""
        config = _make_vault(
            tmp_path,
            {
                "public-only.md": {
                    "content": "---\ntitle: Public\npublic: true\n---\nPublic.\n",
                },
                "published.md": {
                    "content": "---\ntitle: Published\npublic: true\npublished: true\n---\nPublished.\n",
                },
                "private.md": {
                    "content": "---\ntitle: Private\n---\nPrivate.\n",
                },
            },
        )
        report = scan_status(config)
        assert len(report.pages) == 3
        assert len(report.public_pages) == 2
        assert len(report.published_pages) == 1
        assert len(report.private_pages) == 1
        assert len(report.new_pages) == 2

    def test_global_config_change_marks_pages_modified(self, tmp_path):
        """Config mtime changes should mark existing pages as modified."""
        import os
        import time

        from foliate.build import build

        config = _make_vault(
            tmp_path,
            {
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
        )
        build(config=config, force_rebuild=True)

        # Touch config with mtime clearly in the future
        assert config.config_path is not None
        config.config_path.write_text(config.config_path.read_text() + "\n# updated\n")
        future = time.time() + 2
        os.utime(config.config_path, (future, future))

        report = scan_status(config)
        assert report.public_pages[0].state == "modified"
        assert len(report.modified_pages) == 1

    def test_incremental_disabled_marks_existing_pages_modified(self, tmp_path):
        """With incremental=false, existing pages should be reported as rebuilt."""
        from foliate.build import build

        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test Site"
url = "https://test.com"

[build]
home_redirect = "about"
incremental = false
"""
        )
        (vault_path / "test.md").write_text(
            "---\ntitle: Test\npublic: true\n---\nHello.\n"
        )

        config = Config.load(config_path)
        build(config=config, force_rebuild=True)

        report = scan_status(config)
        assert report.public_pages[0].state == "modified"
        assert len(report.modified_pages) == 1

    def test_private_published_page_not_counted_as_published(self, tmp_path):
        """Private pages should never count toward published totals."""
        config = _make_vault(
            tmp_path,
            {
                "public.md": {
                    "content": "---\ntitle: Public\npublic: true\npublished: true\n---\nPublic.\n",
                },
                "private.md": {
                    "content": "---\ntitle: Private\npublished: true\n---\nPrivate.\n",
                },
            },
        )
        report = scan_status(config)
        assert len(report.public_pages) == 1
        assert len(report.published_pages) == 1
        assert report.published_pages[0].page_path == "public"


class TestPageStatus:
    """Tests for PageStatus dataclass."""

    def test_output_url_wiki(self):
        """Wiki pages have /wiki/ prefix in URL."""
        ps = PageStatus(
            page_path="Notes/Ideas",
            source_file=None,
            base_url="/wiki/",
            is_homepage_content=False,
            public=True,
            published=False,
            state="new",
        )
        assert ps.output_url == "/wiki/Notes/Ideas/"

    def test_output_url_homepage(self):
        """Homepage pages have / prefix in URL."""
        ps = PageStatus(
            page_path="about",
            source_file=None,
            base_url="/",
            is_homepage_content=True,
            public=True,
            published=False,
            state="new",
        )
        assert ps.output_url == "/about/"


class TestFormatStatusReport:
    """Tests for format_status_report()."""

    def test_empty_report(self):
        """Empty report shows zeroes."""
        report = StatusReport(pages=[])
        output = format_status_report(report)
        assert "0 public" in output
        assert "0 new" in output

    def test_new_pages_shown(self):
        """New pages appear with + prefix."""
        pages = [
            PageStatus("test", None, "/wiki/", False, True, False, "new"),
        ]
        report = StatusReport(pages=pages)
        output = format_status_report(report)
        assert "+ test" in output
        assert "1 new" in output

    def test_modified_pages_shown(self):
        """Modified pages appear with ~ prefix."""
        pages = [
            PageStatus("test", None, "/wiki/", False, True, False, "modified"),
        ]
        report = StatusReport(pages=pages)
        output = format_status_report(report)
        assert "~ test" in output
        assert "1 modified" in output

    def test_unchanged_hidden_without_verbose(self):
        """Unchanged pages are hidden by default."""
        pages = [
            PageStatus("test", None, "/wiki/", False, True, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)
        output = format_status_report(report, verbose=False)
        assert "Unchanged" not in output

    def test_unchanged_shown_with_verbose(self):
        """Unchanged pages are shown with --verbose."""
        pages = [
            PageStatus("test", None, "/wiki/", False, True, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)
        output = format_status_report(report, verbose=True)
        assert "Unchanged" in output
        assert "test" in output

    def test_published_tag_shown(self):
        """Published pages get [published] tag."""
        pages = [
            PageStatus("blog", None, "/wiki/", False, True, True, "new"),
        ]
        report = StatusReport(pages=pages)
        output = format_status_report(report)
        assert "[published]" in output

    def test_summary_counts_only_public_published_pages(self):
        """Summary should ignore private pages even if published=true."""
        pages = [
            PageStatus("public", None, "/wiki/", False, True, True, "new"),
            PageStatus("private", None, "/wiki/", False, False, True, "unchanged"),
        ]
        report = StatusReport(pages=pages)
        output = format_status_report(report)
        assert "1 published" in output


class TestFormatBuildDryRunReport:
    """Tests for format_build_dry_run_report()."""

    def test_normal_mode_shows_new_and_modified(self):
        """Non-force mode shows only new and modified pages."""
        from foliate.status import format_build_dry_run_report

        pages = [
            PageStatus("new-page", None, "/wiki/", False, True, False, "new"),
            PageStatus("mod-page", None, "/wiki/", False, True, False, "modified"),
            PageStatus("old-page", None, "/wiki/", False, True, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)
        output = format_build_dry_run_report(report)
        assert "Would build (2)" in output
        assert "new-page" in output
        assert "mod-page" in output
        assert "old-page" not in output

    def test_force_rebuild_shows_all_public(self):
        """Force rebuild mode shows all public pages."""
        from foliate.status import format_build_dry_run_report

        pages = [
            PageStatus("page-a", None, "/wiki/", False, True, False, "new"),
            PageStatus("page-b", None, "/wiki/", False, True, False, "unchanged"),
            PageStatus("private", None, "/wiki/", False, False, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)
        output = format_build_dry_run_report(report, force_rebuild=True)
        assert "Would build (2)" in output
        assert "page-a" in output
        assert "page-b" in output
        assert "(forced)" in output

    def test_verbose_shows_unchanged(self):
        """Verbose mode shows cached/unchanged pages."""
        from foliate.status import format_build_dry_run_report

        pages = [
            PageStatus("new-page", None, "/wiki/", False, True, False, "new"),
            PageStatus("cached", None, "/wiki/", False, True, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)

        output_quiet = format_build_dry_run_report(report, verbose=False)
        assert "Cached/unchanged" not in output_quiet

        output_verbose = format_build_dry_run_report(report, verbose=True)
        assert "Cached/unchanged (1)" in output_verbose
        assert "cached" in output_verbose

    def test_private_pages_count_only_without_verbose(self):
        """Private pages show count only without verbose."""
        from foliate.status import format_build_dry_run_report

        pages = [
            PageStatus("public", None, "/wiki/", False, True, False, "new"),
            PageStatus("secret-a", None, "/wiki/", False, False, False, "unchanged"),
            PageStatus("secret-b", None, "/wiki/", False, False, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)

        output = format_build_dry_run_report(report, verbose=False)
        assert "Private pages (2, skipped)" in output
        assert "secret-a" not in output

    def test_private_pages_listed_with_verbose(self):
        """Private pages are listed individually with verbose."""
        from foliate.status import format_build_dry_run_report

        pages = [
            PageStatus("public", None, "/wiki/", False, True, False, "new"),
            PageStatus("secret-a", None, "/wiki/", False, False, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)

        output = format_build_dry_run_report(report, verbose=True)
        assert "Private pages (1, skipped)" in output
        assert "secret-a" in output

    def test_summary_line(self):
        """Summary line has correct counts."""
        from foliate.status import format_build_dry_run_report

        pages = [
            PageStatus("pub1", None, "/wiki/", False, True, True, "new"),
            PageStatus("pub2", None, "/wiki/", False, True, False, "modified"),
            PageStatus("priv", None, "/wiki/", False, False, False, "unchanged"),
        ]
        report = StatusReport(pages=pages)
        output = format_build_dry_run_report(report)
        assert "2 public" in output
        assert "1 published" in output
        assert "2 would build" in output
        assert "1 private" in output

    def test_dry_run_header(self):
        """Output starts with dry run notice."""
        from foliate.status import format_build_dry_run_report

        report = StatusReport(pages=[])
        output = format_build_dry_run_report(report)
        assert output.startswith("Dry run: no files will be written.")
