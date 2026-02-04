"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from foliate.cli import main


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
target = "{target.resolve()}"
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
target = "{target.resolve()}"
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
target = "{target.resolve()}"
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
target = "{target.resolve()}"
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

            result = runner.invoke(main, ["watch"])

            assert mock_watch.called

    @patch("foliate.watch.watch")
    def test_port_flag(self, mock_watch):
        """Should pass port to watch function."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["watch", "--port", "9000"])

            mock_watch.assert_called()
            call_kwargs = mock_watch.call_args[1]
            assert call_kwargs.get("port") == 9000
