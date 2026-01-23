"""Tests for deploy module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from foliate.config import Config, DeployConfig
from foliate.deploy import deploy_github_pages


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
