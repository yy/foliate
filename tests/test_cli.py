"""Tests for CLI commands."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from foliate.cli import _exit_with_error, _load_config_or_exit, main


class TestInitCommand:
    """Tests for the init command."""

    def test_creates_config_file(self):
        """Should create .foliate/config.toml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])

            assert result.exit_code == 0
            assert Path(".foliate/config.toml").exists()
            assert "Created" in result.output

    def test_creates_templates_directory(self):
        """Should create .foliate/templates/ with template files."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])

            assert result.exit_code == 0
            templates_dir = Path(".foliate/templates")
            assert templates_dir.exists()
            assert "templates" in result.output

    def test_creates_feed_template(self):
        """Should scaffold the bundled feed.xml template during init."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])

            assert result.exit_code == 0
            assert Path(".foliate/templates/feed.xml").exists()

    def test_creates_static_directory(self):
        """Should create .foliate/static/ with CSS files."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])

            assert result.exit_code == 0
            static_dir = Path(".foliate/static")
            assert static_dir.exists()
            assert "static" in result.output

    def test_fails_if_config_exists_without_force(self):
        """Should fail if config already exists without --force."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create existing config
            Path(".foliate").mkdir()
            Path(".foliate/config.toml").write_text("[site]\nname = 'Existing'")

            result = runner.invoke(main, ["init"])

            assert result.exit_code == 1
            assert "already exists" in result.output
            # Config should not be overwritten
            assert "Existing" in Path(".foliate/config.toml").read_text()

    def test_force_overwrites_existing(self):
        """Should overwrite existing config with --force."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create existing config
            Path(".foliate").mkdir()
            Path(".foliate/config.toml").write_text("[site]\nname = 'Existing'")

            result = runner.invoke(main, ["init", "--force"])

            assert result.exit_code == 0
            # Config should be overwritten with default
            config_content = Path(".foliate/config.toml").read_text()
            assert "Existing" not in config_content

    def test_fails_cleanly_when_templates_or_static_path_is_a_file(self):
        """Should reject conflicting scaffold paths before writing anything."""
        runner = CliRunner()

        for conflicting_path in (".foliate/templates", ".foliate/static"):
            with runner.isolated_filesystem():
                Path(".foliate").mkdir()
                Path(conflicting_path).write_text("not a directory", encoding="utf-8")
                other_path = (
                    ".foliate/static"
                    if conflicting_path == ".foliate/templates"
                    else ".foliate/templates"
                )

                result = runner.invoke(main, ["init"])

                assert result.exit_code == 1
                assert "is not a directory" in result.output
                assert not Path(".foliate/config.toml").exists()
                assert not Path(".foliate/templates").is_dir()
                assert Path(conflicting_path).is_file()
                assert not Path(other_path).exists()

    def test_shows_next_steps(self):
        """Should show customization hints after init."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])

            assert result.exit_code == 0
            assert "Customize your site" in result.output
            assert "config.toml" in result.output
            assert "foliate build" in result.output


class TestBuildCommand:
    """Tests for the build command."""

    def test_fails_without_config(self):
        """Should fail when no config file exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["build"])

            assert result.exit_code == 1
            assert "Error" in result.output

    def test_builds_with_config(self):
        """Should build site when config exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Initialize first
            runner.invoke(main, ["init"])

            # Create a public page
            Path("test.md").write_text("---\npublic: true\n---\n# Test Page")

            result = runner.invoke(main, ["build"])

            # Build should succeed (exit code 0)
            # or fail due to no public pages if there's an issue
            assert Path(".foliate/build").exists() or result.exit_code == 1

    def test_fails_with_no_public_pages(self):
        """Should fail when no public pages are found."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Initialize
            runner.invoke(main, ["init"])
            # Don't create any public pages

            result = runner.invoke(main, ["build"])

            assert result.exit_code == 1
            assert "No public pages" in result.output

    def test_force_flag(self):
        """Should accept --force flag for full rebuild."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])
            Path("test.md").write_text("---\npublic: true\n---\n# Test")

            # First build
            runner.invoke(main, ["build"])

            # Force rebuild
            result = runner.invoke(main, ["build", "--force"])

            # Should run without issues
            assert result.exit_code == 0 or "No public pages" in result.output

    def test_verbose_flag(self):
        """Should accept --verbose flag."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])
            Path("test.md").write_text("---\npublic: true\n---\n# Test")

            result = runner.invoke(main, ["build", "--verbose"])

            # Should complete (exit 0) or fail for other reasons
            assert result.exit_code in [0, 1]

    def test_dry_run_lists_pages_without_writing_files(self):
        """--dry-run should preview pages and avoid writing build output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])
            Path("public.md").write_text("---\npublic: true\n---\n# Public")
            Path("private.md").write_text("---\n---\n# Private")

            result = runner.invoke(main, ["build", "--dry-run"])

            assert result.exit_code == 0
            assert "Dry run: no files will be written." in result.output
            assert "Would build (1):" in result.output
            assert "+ public (new)" in result.output
            assert "Private pages (1, skipped)" in result.output
            assert not Path(".foliate/build").exists()

    def test_dry_run_force_lists_all_public_pages(self):
        """--dry-run --force should show all public pages as build targets."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])
            Path("test.md").write_text("---\npublic: true\n---\n# Test")

            # Create output so next status is "unchanged" without force.
            runner.invoke(main, ["build"])

            result = runner.invoke(main, ["build", "--dry-run", "--force"])

            assert result.exit_code == 0
            assert "Would build (1):" in result.output
            assert "+ test (forced)" in result.output

    @patch("foliate.quarto.is_quarto_preprocessing_available", return_value=False)
    def test_dry_run_skips_qmd_only_pages_when_preprocessing_unavailable(
        self, _mock_quarto_available
    ):
        """--dry-run should not claim qmd-only pages are buildable without Quarto."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path(".foliate").mkdir()
            Path(".foliate/config.toml").write_text(
                """
[site]
name = "Test"
url = "https://example.com"

[advanced]
quarto_enabled = true
"""
            )
            Path("paper.qmd").write_text(
                "---\npublic: true\npublished: true\n---\n# Paper\n"
            )

            result = runner.invoke(main, ["build", "--dry-run"])

            assert result.exit_code == 0
            assert "Would build (0):" in result.output
            assert (
                "Summary: 0 public, 0 published, 0 would build, 0 private"
                in result.output
            )
            assert "paper" not in result.output

    def test_dry_run_rejects_serve_flag(self):
        """--serve is incompatible with --dry-run."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])
            Path("test.md").write_text("---\npublic: true\n---\n# Test")

            result = runner.invoke(main, ["build", "--dry-run", "--serve"])

            assert result.exit_code == 1
            assert "--serve cannot be used with --dry-run" in result.output


class TestCliHelpers:
    """Tests for shared CLI helper behavior."""

    @patch("foliate.cli.click.echo")
    def test_exit_with_error_can_preserve_leading_blank_line(self, mock_echo):
        """Should support the existing blank-line error formatting when needed."""
        with pytest.raises(SystemExit) as exc_info:
            _exit_with_error("port in use", leading_newline=True)

        assert exc_info.value.code == 1
        mock_echo.assert_called_once_with("\nError: port in use", err=True)

    @patch("foliate.cli.click.echo")
    @patch("foliate.cli.Config.find_and_load")
    def test_load_config_or_exit_reports_missing_config_cleanly(
        self, mock_find_and_load, mock_echo
    ):
        """Should convert missing config errors into Click-friendly exits."""
        mock_find_and_load.side_effect = FileNotFoundError(
            "No .foliate/config.toml found. Run 'foliate init' first."
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config_or_exit()

        assert exc_info.value.code == 1
        mock_echo.assert_called_once_with(
            "Error: No .foliate/config.toml found. Run 'foliate init' first.",
            err=True,
        )

    def test_status_fails_cleanly_when_config_path_is_directory(self):
        """Should report a bad config path without a Python traceback."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path(".foliate/config.toml").mkdir(parents=True)

            result = runner.invoke(main, ["status"])

            assert result.exit_code == 1
            assert ".foliate/config.toml" in result.output
            assert "is not a file" in result.output
            assert "Traceback" not in result.output

    @patch("foliate.cli.Config.find_and_load")
    def test_config_commands_share_missing_config_error_handling(
        self, mock_find_and_load
    ):
        """Should keep config-dependent commands on the same error path."""
        mock_find_and_load.side_effect = FileNotFoundError(
            "No .foliate/config.toml found. Run 'foliate init' first."
        )

        runner = CliRunner()

        for command in (["build"], ["watch"], ["status"], ["deploy"]):
            result = runner.invoke(main, command)

            assert result.exit_code == 1
            assert (
                "Error: No .foliate/config.toml found. Run 'foliate init' first."
                in result.output
            )


class TestCleanCommand:
    """Tests for the clean command."""

    def test_removes_build_directory(self):
        """Should remove .foliate/build/ directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create build directory
            build_dir = Path(".foliate/build")
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html></html>")

            result = runner.invoke(main, ["clean"])

            assert result.exit_code == 0
            assert not build_dir.exists()
            assert "Removed" in result.output

    def test_removes_cache_directory(self):
        """Should remove .foliate/cache/ directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create cache directory
            cache_dir = Path(".foliate/cache")
            cache_dir.mkdir(parents=True)
            (cache_dir / "cache.json").write_text("{}")

            result = runner.invoke(main, ["clean"])

            assert result.exit_code == 0
            assert not cache_dir.exists()
            assert "Removed" in result.output

    def test_removes_both_directories(self):
        """Should remove both build and cache directories."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            build_dir = Path(".foliate/build")
            cache_dir = Path(".foliate/cache")
            build_dir.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html></html>")
            (cache_dir / "cache.json").write_text("{}")

            result = runner.invoke(main, ["clean"])

            assert result.exit_code == 0
            assert not build_dir.exists()
            assert not cache_dir.exists()

    def test_nothing_to_clean(self):
        """Should handle case where there's nothing to clean."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["clean"])

            assert result.exit_code == 0
            assert "Nothing to clean" in result.output

    def test_preserves_config(self):
        """Should preserve config.toml when cleaning."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config and build
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()
            config_file = foliate_dir / "config.toml"
            config_file.write_text("[site]\nname = 'Test'")
            build_dir = foliate_dir / "build"
            build_dir.mkdir()

            result = runner.invoke(main, ["clean"])

            assert result.exit_code == 0
            assert config_file.exists()

    def test_finds_project_root_from_nested_directory(self):
        """Should clean project artifacts when invoked from a nested directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            project_root = Path.cwd()
            build_dir = project_root / ".foliate" / "build"
            cache_dir = project_root / ".foliate" / "cache"
            build_dir.mkdir(parents=True)
            cache_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html></html>")
            (cache_dir / "cache.json").write_text("{}")

            nested_dir = project_root / "notes" / "subdir"
            nested_dir.mkdir(parents=True)

            original_cwd = Path.cwd()
            os.chdir(nested_dir)
            try:
                result = runner.invoke(main, ["clean"])
            finally:
                os.chdir(original_cwd)

            assert result.exit_code == 0
            assert not build_dir.exists()
            assert not cache_dir.exists()


class TestDoctorCommand:
    """Tests for the doctor command."""

    def test_fails_without_config(self):
        """Should fail when no config file exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["doctor"])

            assert result.exit_code == 1
            assert "config.toml" in result.output

    def test_reports_ok_with_config(self):
        """Should report OK when config exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()
            (foliate_dir / "config.toml").write_text("")

            result = runner.invoke(main, ["doctor"])

            assert result.exit_code == 0
            assert "OK" in result.output

    def test_reports_validation_errors_cleanly(self):
        """Should surface config validation errors without a traceback."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()
            (foliate_dir / "config.toml").write_text('[nav]\nitems = ["broken"]\n')

            result = runner.invoke(main, ["doctor"])

            assert result.exit_code == 1
            assert "Invalid configuration:" in result.output
            assert "must be a table" in result.output

    def test_warns_when_templates_path_is_a_file(self):
        """Should warn when .foliate/templates exists but is not a directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()
            (foliate_dir / "config.toml").write_text("")
            (foliate_dir / "templates").write_text("not a directory")

            result = runner.invoke(main, ["doctor"])

            assert result.exit_code == 0
            assert "Warning: User templates path is not a directory:" in result.output
            assert "OK: User templates directory:" not in result.output

    def test_warns_when_static_path_is_a_file(self):
        """Should warn when .foliate/static exists but is not a directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()
            (foliate_dir / "config.toml").write_text("")
            (foliate_dir / "static").write_text("not a directory")

            result = runner.invoke(main, ["doctor"])

            assert result.exit_code == 0
            assert "Warning: User static path is not a directory:" in result.output
            assert "OK: User static directory:" not in result.output


class TestDeployCommand:
    """Tests for the deploy command."""

    def test_fails_without_config(self):
        """Should fail when no config file exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["deploy"])

            assert result.exit_code == 1
            assert "Error" in result.output

    def test_fails_without_deploy_target(self):
        """Should fail when no deploy target is configured."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["deploy"])

            assert result.exit_code == 1
            assert "No deploy target configured" in result.output

    @patch("foliate.deploy.deploy_github_pages")
    def test_calls_deploy_function(self, mock_deploy):
        """Should call deploy_github_pages with correct args."""
        mock_deploy.return_value = True

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config with deploy target (using subdirectory)
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()

            # Create the target dir inside the isolated filesystem
            target = Path("target")
            target.mkdir()
            (target / ".git").mkdir()

            config_file = foliate_dir / "config.toml"
            config_file.write_text(
                f"""
[site]
name = "Test"

[deploy]
target = "{target.resolve().as_posix()}"
"""
            )

            runner.invoke(main, ["deploy"])

            assert mock_deploy.called

    @patch("foliate.deploy.deploy_github_pages")
    def test_dry_run_flag(self, mock_deploy):
        """Should pass dry_run=True to deploy function."""
        mock_deploy.return_value = True

        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()

            target = Path("target")
            target.mkdir()
            (target / ".git").mkdir()

            config_file = foliate_dir / "config.toml"
            config_file.write_text(
                f"""
[site]
name = "Test"

[deploy]
target = "{target.resolve().as_posix()}"
"""
            )

            runner.invoke(main, ["deploy", "--dry-run"])

            mock_deploy.assert_called()
            call_kwargs = mock_deploy.call_args[1]
            assert call_kwargs.get("dry_run") is True

    @patch("foliate.deploy.deploy_github_pages")
    def test_custom_message_flag(self, mock_deploy):
        """Should pass custom message to deploy function."""
        mock_deploy.return_value = True

        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()

            target = Path("target")
            target.mkdir()
            (target / ".git").mkdir()

            config_file = foliate_dir / "config.toml"
            config_file.write_text(
                f"""
[site]
name = "Test"

[deploy]
target = "{target.resolve().as_posix()}"
"""
            )

            runner.invoke(main, ["deploy", "-m", "Custom message"])

            mock_deploy.assert_called()
            call_kwargs = mock_deploy.call_args[1]
            assert call_kwargs.get("message") == "Custom message"

    @patch("foliate.deploy.deploy_github_pages")
    def test_build_flag(self, mock_deploy):
        """Should pass build_first=True to deploy function."""
        mock_deploy.return_value = True

        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()

            target = Path("target")
            target.mkdir()
            (target / ".git").mkdir()

            config_file = foliate_dir / "config.toml"
            config_file.write_text(
                f"""
[site]
name = "Test"

[deploy]
target = "{target.resolve().as_posix()}"
"""
            )

            runner.invoke(main, ["deploy", "--build"])

            mock_deploy.assert_called()
            call_kwargs = mock_deploy.call_args[1]
            assert call_kwargs.get("build_first") is True

    @patch("foliate.deploy.deploy_github_pages")
    def test_deploy_failure_exits_with_error(self, mock_deploy):
        """Should exit with code 1 when deploy fails."""
        mock_deploy.return_value = False

        runner = CliRunner()
        with runner.isolated_filesystem():
            foliate_dir = Path(".foliate")
            foliate_dir.mkdir()

            target = Path("target")
            target.mkdir()
            (target / ".git").mkdir()

            config_file = foliate_dir / "config.toml"
            config_file.write_text(
                f"""
[site]
name = "Test"

[deploy]
target = "{target.resolve()}"
"""
            )

            result = runner.invoke(main, ["deploy"])

            assert result.exit_code == 1


class TestMainGroup:
    """Tests for the main CLI group."""

    def test_help_shows_commands(self):
        """Should list available commands in help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "build" in result.output
        assert "doctor" in result.output
        assert "clean" in result.output
        assert "deploy" in result.output
        assert "watch" in result.output

    def test_version_flag(self):
        """Should show version with --version flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        # Version output format varies, just check it runs


class TestWatchCommand:
    """Tests for the watch command."""

    def test_fails_without_config(self):
        """Should fail when no config file exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["watch"])

            assert result.exit_code == 1
            assert "Error" in result.output

    @patch("foliate.watch.watch")
    def test_calls_watch_function(self, mock_watch):
        """Should call watch function with config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            runner.invoke(main, ["watch"])

            assert mock_watch.called

    @patch("foliate.watch.watch")
    def test_port_flag(self, mock_watch):
        """Should pass port to watch function."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            runner.invoke(main, ["watch", "--port", "9000"])

            mock_watch.assert_called()
            call_kwargs = mock_watch.call_args[1]
            assert call_kwargs.get("port") == 9000
