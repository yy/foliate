"""Tests for foliate status module."""

import os
import subprocess
import time

from foliate.config import Config
from foliate.status import (
    PageStatus,
    StatusReport,
    format_status_report,
    scan_status,
)

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@test.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@test.com",
}


def _git_init_and_commit(path, message="deploy"):
    """Initialize a git repo and make a commit with all files."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=path,
        capture_output=True,
        check=True,
        env=_GIT_ENV,
    )


def _make_vault_with_deploy(
    tmp_path, pages: dict[str, dict], deploy_pages: dict[str, str] | None = None
) -> Config:
    """Create a vault with a deploy target and return a Config.

    Args:
        tmp_path: pytest tmp_path fixture
        pages: dict mapping relative file paths to dicts with "content" key
        deploy_pages: dict mapping output paths (e.g. "wiki/test/index.html")
                      to HTML content in the deploy target
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    deploy_path = tmp_path / "deploy"
    deploy_path.mkdir()

    foliate_dir = vault_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text(
        f"""
[site]
name = "Test Site"
url = "https://test.com"

[build]
home_redirect = "about"

[deploy]
target = "{deploy_path.as_posix()}"
"""
    )

    for rel_path, info in pages.items():
        md_file = vault_path / rel_path
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text(info["content"])

    # Set source file mtimes to 2 seconds in the past so they are clearly
    # older than the deploy commit (git timestamps are whole seconds).
    past = time.time() - 2
    for rel_path in pages:
        md_file = vault_path / rel_path
        os.utime(md_file, (past, past))

    if deploy_pages:
        for rel_path, content in deploy_pages.items():
            out_file = deploy_path / rel_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(content)

    # Initialize deploy dir as a git repo with a commit
    _git_init_and_commit(deploy_path)

    return Config.load(config_path)


def _make_vault(tmp_path, pages: dict[str, dict]) -> Config:
    """Create a vault with pages and return a Config.

    Args:
        tmp_path: pytest tmp_path fixture
        pages: dict mapping relative file paths (e.g. "test.md") to dicts
               with keys: content (str), and optionally a subdir like
               "_homepage/about.md"
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

    def test_uppercase_markdown_extension_is_included(self, tmp_path):
        """Uppercase .MD files should appear in status scans."""
        config = _make_vault(
            tmp_path,
            {
                "Guide.MD": {
                    "content": "---\ntitle: Guide\npublic: true\n---\nHello.\n",
                },
            },
        )

        report = scan_status(config)

        assert len(report.public_pages) == 1
        assert report.public_pages[0].page_path == "Guide"
        assert report.public_pages[0].state == "new"

    def test_prefers_lowercase_markdown_when_case_variants_exist(self, tmp_path):
        """Status should match build selection for duplicate extension variants."""
        config = _make_vault(
            tmp_path,
            {
                "Guide.md": {
                    "content": "---\ntitle: Guide\npublic: true\n---\nLower.\n",
                },
                "Guide.MD": {
                    "content": "---\ntitle: Guide\npublic: true\n---\nUpper.\n",
                },
            },
        )

        report = scan_status(config)

        assert len(report.public_pages) == 1
        assert report.public_pages[0].source_file.name == "Guide.md"

    def test_published_page_detected(self, tmp_path):
        """Published pages are reported correctly."""
        config = _make_vault(
            tmp_path,
            {
                "blog.md": {
                    "content": (
                        "---\ntitle: Blog\npublic: true\npublished: true\n---\nPost.\n"
                    ),
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

    def test_homepage_and_wiki_pages_with_same_path_are_reported_separately(
        self, tmp_path
    ):
        """Status should keep homepage and wiki namespaces distinct."""
        config = _make_vault(
            tmp_path,
            {
                "_homepage/about.md": {
                    "content": "---\ntitle: About\npublic: true\n---\nHomepage.\n",
                },
                "about.md": {
                    "content": "---\ntitle: About Wiki\npublic: true\n---\nWiki.\n",
                },
            },
        )

        report = scan_status(config)

        assert len(report.public_pages) == 2
        assert {
            (page.page_path, page.base_url, page.is_homepage_content)
            for page in report.public_pages
        } == {
            ("about", "/", True),
            ("about", "/wiki/", False),
        }

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
                    "content": (
                        "---\ntitle: Published\npublic: true\npublished: true\n"
                        "---\nPublished.\n"
                    ),
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

    def test_global_config_change_does_not_affect_status(self, tmp_path):
        """Config-only changes don't mark pages as modified (source unchanged)."""

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
        assert report.public_pages[0].state == "unchanged"
        assert len(report.unchanged_pages) == 1

    def test_incremental_disabled_does_not_affect_status(self, tmp_path):
        """With incremental=false, status uses mtime comparison not cache."""
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
        assert report.public_pages[0].state == "unchanged"
        assert len(report.unchanged_pages) == 1

    def test_private_published_page_not_counted_as_published(self, tmp_path):
        """Private pages should never count toward published totals."""
        config = _make_vault(
            tmp_path,
            {
                "public.md": {
                    "content": (
                        "---\ntitle: Public\npublic: true\npublished: true\n"
                        "---\nPublic.\n"
                    ),
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

    def test_quarto_status_prefers_rendered_markdown_over_qmd(self, tmp_path):
        """Status should not double-count a Quarto source and its rendered markdown."""
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

[advanced]
quarto_enabled = true
"""
        )

        (vault_path / "paper.qmd").write_text(
            "---\ntitle: Paper\npublic: true\npublished: true\n---\n# Source\n"
        )
        (vault_path / "paper.md").write_text(
            "---\ntitle: Paper\npublic: true\npublished: true\n---\n# Rendered\n"
        )

        config = Config.load(config_path)
        report = scan_status(config)

        assert len(report.pages) == 1
        assert report.pages[0].page_path == "paper"
        assert report.pages[0].source_file.name == "paper.md"
        assert len(report.public_pages) == 1

    def test_qmd_only_page_skipped_when_preprocessing_unavailable(
        self, tmp_path, monkeypatch
    ):
        """QMD-only pages should not appear when Quarto preprocessing cannot run."""
        monkeypatch.setattr(
            "foliate.status.is_quarto_preprocessing_available", lambda: False
        )
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

[advanced]
quarto_enabled = true
"""
        )

        (vault_path / "paper.qmd").write_text(
            "---\ntitle: Paper\npublic: true\npublished: true\n---\n# Source\n"
        )

        config = Config.load(config_path)
        report = scan_status(config)

        assert report.pages == []
        assert report.public_pages == []

    def test_qmd_only_page_included_when_preprocessing_available(
        self, tmp_path, monkeypatch
    ):
        """QMD-only pages should appear when Quarto preprocessing is available."""
        monkeypatch.setattr(
            "foliate.status.is_quarto_preprocessing_available", lambda: True
        )
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

[advanced]
quarto_enabled = true
"""
        )

        (vault_path / "paper.qmd").write_text(
            "---\ntitle: Paper\npublic: true\npublished: true\n---\n# Source\n"
        )

        config = Config.load(config_path)
        report = scan_status(config)

        assert len(report.pages) == 1
        assert report.pages[0].page_path == "paper"
        assert report.pages[0].source_file.name == "paper.qmd"


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


class TestDeployTargetComparison:
    """Tests for status comparison against deploy target."""

    def test_new_page_not_in_deploy_target(self, tmp_path):
        """Public page not in deploy target shows as 'new'."""
        config = _make_vault_with_deploy(
            tmp_path,
            pages={
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
            deploy_pages={},  # empty deploy target
        )
        report = scan_status(config)
        assert len(report.new_pages) == 1
        assert report.new_pages[0].state == "new"
        assert report.deploy_target is not None

    def test_page_already_deployed_is_unchanged(self, tmp_path):
        """Public page that exists in deploy target shows as 'unchanged'.

        Source was created before the deploy commit, so source mtime < commit time.
        """
        config = _make_vault_with_deploy(
            tmp_path,
            pages={
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
            deploy_pages={
                "wiki/test/index.html": "<html>old</html>",
            },
        )
        # _make_vault_with_deploy creates source files first, then makes a git
        # commit in the deploy dir. So source mtime < last deploy commit time.
        report = scan_status(config)
        assert len(report.unchanged_pages) == 1
        assert report.unchanged_pages[0].state == "unchanged"

    def test_modified_page_source_newer_than_deploy(self, tmp_path):
        """Page with source newer than last deploy commit shows as 'modified'."""

        config = _make_vault_with_deploy(
            tmp_path,
            pages={
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
            deploy_pages={
                "wiki/test/index.html": "<html>old</html>",
            },
        )
        # Touch source file to be clearly in the future (after deploy commit)
        md_file = config.vault_path / "test.md"
        future = time.time() + 2
        os.utime(md_file, (future, future))

        report = scan_status(config)
        assert len(report.modified_pages) == 1
        assert report.modified_pages[0].state == "modified"

    def test_deploy_target_shown_in_report(self, tmp_path):
        """Format report shows deploy target path."""
        config = _make_vault_with_deploy(
            tmp_path,
            pages={
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
        )
        report = scan_status(config)
        output = format_status_report(report)
        assert "Comparing against deploy target:" in output

    def test_no_changes_message(self, tmp_path):
        """When everything is deployed, show 'no new or modified' message."""
        config = _make_vault_with_deploy(
            tmp_path,
            pages={
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
            deploy_pages={
                "wiki/test/index.html": "<html>deployed</html>",
            },
        )
        # Source was created before deploy commit → unchanged
        report = scan_status(config)
        output = format_status_report(report)
        assert "No new or modified pages." in output

    def test_homepage_page_new_in_deploy(self, tmp_path):
        """Homepage content not in deploy target shows as 'new'."""
        config = _make_vault_with_deploy(
            tmp_path,
            pages={
                "_homepage/about.md": {
                    "content": "---\ntitle: About\npublic: true\n---\nAbout.\n",
                },
            },
            deploy_pages={},
        )
        report = scan_status(config)
        assert len(report.new_pages) == 1
        assert report.new_pages[0].page_path == "about"
        assert report.new_pages[0].is_homepage_content is True

    def test_fallback_to_build_dir_without_deploy_target(self, tmp_path):
        """Without deploy target, falls back to build-dir comparison."""
        config = _make_vault(
            tmp_path,
            {
                "test.md": {
                    "content": "---\ntitle: Test\npublic: true\n---\nHello.\n",
                },
            },
        )
        report = scan_status(config)
        assert report.deploy_target is None
        # Without build output, should be "new" (build-dir comparison)
        assert len(report.new_pages) == 1

    def test_non_git_deploy_target_uses_file_mtime_fallback(self, tmp_path):
        """Non-git deploy target compares source mtime against deployed file mtime."""
        import os

        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        deploy_path = tmp_path / "deploy"
        deploy_path.mkdir()

        foliate_dir = vault_path / ".foliate"
        foliate_dir.mkdir()
        config_path = foliate_dir / "config.toml"
        config_path.write_text(
            f"""
[site]
name = "Test Site"
url = "https://test.com"

[build]
home_redirect = "about"

[deploy]
target = "{deploy_path.as_posix()}"
"""
        )

        md_file = vault_path / "test.md"
        md_file.write_text("---\ntitle: Test\npublic: true\n---\nHello.\n")
        deploy_file = deploy_path / "wiki" / "test" / "index.html"
        deploy_file.parent.mkdir(parents=True, exist_ok=True)
        deploy_file.write_text("<html>deployed</html>")

        # Simulate source older than deployed output.
        older = deploy_file.stat().st_mtime - 10
        os.utime(md_file, (older, older))

        config = Config.load(config_path)
        report = scan_status(config)

        assert len(report.unchanged_pages) == 1
        assert report.unchanged_pages[0].state == "unchanged"
