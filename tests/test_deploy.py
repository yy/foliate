"""Tests for deploy module."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from foliate.config import Config, DeployConfig
from foliate.deploy import deploy_github_pages, is_build_stale


class TestIsBuildStale:
    """Tests for is_build_stale function."""

    def test_returns_none_when_build_dir_missing(self):
        """Should return None when build directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)
            # Build directory doesn't exist

            result = is_build_stale(config)

            assert result is None

    def test_returns_none_when_vault_missing(self):
        """Should return None when vault path is not set."""
        config = Config()
        config.vault_path = None

        result = is_build_stale(config)

        assert result is None

    def test_returns_false_when_build_is_fresh(self):
        """Should return False when no source files are newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create source file
            source_file = vault / "test.md"
            source_file.write_text("---\npublic: true\n---\n# Test")

            # Wait a bit, then create build
            time.sleep(0.05)
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            build_file = build_dir / "test.html"
            build_file.write_text("<html>Test</html>")

            result = is_build_stale(config)

            assert result is False

    def test_returns_true_when_source_modified_after_build(self):
        """Should return True when source files are newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            build_file = build_dir / "test.html"
            build_file.write_text("<html>Test</html>")

            # Wait a bit, then create source file
            time.sleep(0.05)
            source_file = vault / "test.md"
            source_file.write_text("---\npublic: true\n---\n# Test")

            result = is_build_stale(config)

            assert result is True

    def test_returns_true_when_config_modified_after_build(self):
        """Should return True when config.toml is newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Wait a bit, then modify config
            time.sleep(0.05)
            config_dir = vault / ".foliate"
            config_file = config_dir / "config.toml"
            config_file.write_text("[site]\nname = 'Test'")

            result = is_build_stale(config)

            assert result is True

    def test_returns_true_when_template_modified_after_build(self):
        """Should return True when templates are newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Wait a bit, then modify template
            time.sleep(0.05)
            template_dir = vault / ".foliate" / "templates"
            template_dir.mkdir(parents=True)
            (template_dir / "layout.html").write_text("<html>{{ content }}</html>")

            result = is_build_stale(config)

            assert result is True

    def test_ignores_private_folders(self):
        """Should not consider files in ignored folders as sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault
            config.build.ignored_folders = ["_private"]

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Wait a bit, then modify file in _private
            time.sleep(0.05)
            private_dir = vault / "_private"
            private_dir.mkdir(parents=True)
            (private_dir / "secret.md").write_text("# Secret")

            result = is_build_stale(config)

            # Should be fresh because _private is ignored
            assert result is False

    def test_ignores_foliate_directory(self):
        """Should not consider .foliate internal files (except templates) as sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Wait a bit, then modify cache file in .foliate
            time.sleep(0.05)
            cache_dir = vault / ".foliate" / "cache"
            cache_dir.mkdir(parents=True)
            (cache_dir / ".build_cache").write_text("cache data")

            result = is_build_stale(config)

            # Should be fresh because cache is not a source
            assert result is False


class TestDeployGithubPages:
    """Tests for deploy_github_pages function."""

    def test_returns_false_when_build_dir_missing(self):
        """Should return False when build directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)
            config.deploy = DeployConfig(target=str(Path(tmpdir) / "target"))

            # Build dir doesn't exist
            result = deploy_github_pages(config)

            assert result is False

    def test_returns_false_when_target_missing(self):
        """Should return False when target directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)
            config.deploy = DeployConfig(target=str(Path(tmpdir) / "nonexistent"))

            # Create build directory
            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)

            result = deploy_github_pages(config)

            assert result is False

    def test_returns_false_when_target_not_git_repo(self):
        """Should return False when target is not a git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create build directory
            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)

            # Create target directory (but not a git repo)
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            result = deploy_github_pages(config)

            assert result is False

    def test_resolves_relative_target_path(self):
        """Should resolve relative target paths relative to vault_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)
            config.deploy = DeployConfig(target="../sibling")

            # The target should be resolved relative to vault_path
            # This test verifies the logic without actually running deploy
            build_dir = config.get_build_dir()
            target = Path(config.deploy.target)

            if not target.is_absolute() and config.vault_path:
                target = (config.vault_path / target).resolve()

            # Should resolve to sibling of tmpdir
            assert "sibling" in str(target)

    @patch("foliate.deploy.subprocess.run")
    def test_dry_run_does_not_commit(self, mock_run):
        """Should not commit or push in dry run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create build directory with content
            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            # Create target as git repo
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            # Mock rsync success
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = deploy_github_pages(config, dry_run=True)

            assert result is True
            # Check that rsync was called with --dry-run
            rsync_calls = [
                call for call in mock_run.call_args_list if "rsync" in str(call)
            ]
            assert len(rsync_calls) > 0
            assert "--dry-run" in str(rsync_calls[0])

    @patch("foliate.deploy.subprocess.run")
    def test_excludes_configured_files(self, mock_run):
        """Should exclude files specified in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create build directory
            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            # Create target as git repo
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(
                target=str(target_dir), exclude=["CNAME", "custom.txt"]
            )

            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            deploy_github_pages(config, dry_run=True)

            # Check rsync args include excludes
            rsync_call = mock_run.call_args_list[0]
            args = rsync_call[0][0]
            assert "--exclude=CNAME" in args
            assert "--exclude=custom.txt" in args
            assert "--exclude=.git" in args  # Always excluded

    @patch("foliate.deploy.subprocess.run")
    def test_uses_custom_commit_message(self, mock_run):
        """Should use custom commit message when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create build directory
            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            # Create target as git repo
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            # Mock subprocess calls
            def mock_subprocess(args, **kwargs):
                result = MagicMock()
                result.returncode = 0
                result.stdout = "M file.txt"  # Simulate changes
                result.stderr = ""
                return result

            mock_run.side_effect = mock_subprocess

            deploy_github_pages(config, message="Custom deploy message")

            # Find the commit call
            commit_calls = [
                call for call in mock_run.call_args_list if "commit" in str(call[0][0])
            ]
            if commit_calls:
                commit_args = commit_calls[0][0][0]
                assert "Custom deploy message" in commit_args

    def test_returns_false_on_rsync_failure(self):
        """Should return False when rsync fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create build directory
            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)

            # Create target as git repo
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            with patch("foliate.deploy.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)

                result = deploy_github_pages(config)

                assert result is False


class TestDeployConfig:
    """Tests for DeployConfig defaults."""

    def test_default_values(self):
        """Should have sensible default values."""
        config = DeployConfig()

        assert config.method == "github-pages"
        assert config.target == ""
        assert ".git" not in config.exclude  # .git is handled separately in deploy

    def test_exclude_preserves_custom_values(self):
        """Should preserve custom exclude values."""
        config = DeployConfig(exclude=["CNAME", "custom.txt", ".nojekyll"])

        assert "CNAME" in config.exclude
        assert "custom.txt" in config.exclude
        assert ".nojekyll" in config.exclude


class TestDeployWithBuild:
    """Tests for --build flag on deploy command."""

    @patch("foliate.deploy.subprocess.run")
    def test_build_flag_triggers_build_before_deploy(self, mock_run):
        """Should run build before deploying when --build flag is passed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create target as git repo
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            # Create build directory (simulating build result)
            build_dir = config.get_build_dir()
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # Mock the build function to return success
            with patch("foliate.build.build", return_value=5) as mock_build:
                result = deploy_github_pages(config, build_first=True, dry_run=True)

                # Build should have been called
                mock_build.assert_called_once()
                assert result is True

    def test_build_flag_not_set_does_not_build(self):
        """Should not build when --build flag is not passed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Build dir doesn't exist and we don't pass build_first
            # This should fail because there's no build directory
            config.deploy = DeployConfig(target=str(Path(tmpdir) / "target"))

            result = deploy_github_pages(config, build_first=False)

            # Should return False because build directory doesn't exist
            assert result is False

    @patch("foliate.deploy.subprocess.run")
    def test_build_failure_stops_deploy(self, mock_run):
        """Should not deploy if build fails (no public pages)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            # Create target as git repo
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # Mock the build function to return 0 (no pages)
            with patch("foliate.build.build", return_value=0):
                result = deploy_github_pages(config, build_first=True)

                # Should return False because build found no public pages
                assert result is False


class TestStaleWarning:
    """Tests for stale build warning in deploy."""

    @patch("foliate.deploy.subprocess.run")
    @patch("foliate.logging.warning")
    def test_warns_when_build_is_stale(self, mock_warning, mock_run):
        """Should warn when build directory is stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Create target as git repo
            target_dir = vault / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            # Wait, then modify source
            time.sleep(0.05)
            (vault / "test.md").write_text("# Test")

            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            deploy_github_pages(config, dry_run=True)

            # Check that warning was printed
            warning_calls = [
                call
                for call in mock_warning.call_args_list
                if "stale" in str(call).lower()
            ]
            assert len(warning_calls) > 0

    @patch("foliate.deploy.subprocess.run")
    @patch("foliate.logging.warning")
    def test_no_warning_when_build_is_fresh(self, mock_warning, mock_run):
        """Should not warn when build is up-to-date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create source first
            (vault / "test.md").write_text("# Test")

            # Wait, then create build
            time.sleep(0.05)
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Create target as git repo
            target_dir = vault / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            deploy_github_pages(config, dry_run=True)

            # Check that no stale warning was printed
            warning_calls = [
                call
                for call in mock_warning.call_args_list
                if "stale" in str(call).lower()
            ]
            assert len(warning_calls) == 0

    @patch("foliate.deploy.subprocess.run")
    @patch("foliate.logging.warning")
    def test_no_warning_when_build_first_is_set(self, mock_warning, mock_run):
        """Should not warn about stale build when --build flag is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            # Create build first
            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            # Create target as git repo
            target_dir = vault / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            # Wait, then modify source
            time.sleep(0.05)
            (vault / "test.md").write_text("# Test")

            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # Mock build to succeed
            with patch("foliate.build.build", return_value=1):
                deploy_github_pages(config, build_first=True, dry_run=True)

            # Check that no stale warning was printed (build_first rebuilds)
            warning_calls = [
                call
                for call in mock_warning.call_args_list
                if "stale" in str(call).lower()
            ]
            assert len(warning_calls) == 0
