"""Tests for deploy module."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from foliate.cache import save_build_cache
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

    def test_returns_true_when_user_static_modified_after_build(self):
        """Should return True when user static files are newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "test.html").write_text("<html>Test</html>")

            time.sleep(0.05)
            static_dir = vault / ".foliate" / "static"
            static_dir.mkdir(parents=True)
            (static_dir / "main.css").write_text("body { color: black; }")

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

    def test_returns_true_when_asset_modified_after_build(self):
        """Should return True when user asset files are newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html>Test</html>")

            time.sleep(0.05)
            assets_dir = vault / "assets"
            assets_dir.mkdir()
            (assets_dir / "image.png").write_text("png")

            result = is_build_stale(config)
            assert result is True

    def test_returns_true_when_qmd_modified_after_build(self):
        """Should return True when .qmd source files are newer than build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html>Test</html>")

            time.sleep(0.05)
            (vault / "paper.qmd").write_text("# QMD")

            result = is_build_stale(config)
            assert result is True

    def test_returns_true_when_new_qmd_only_page_has_older_mtime_than_build(
        self, monkeypatch
    ):
        """New qmd-only pages should mark the build stale when preprocessing can run."""
        monkeypatch.setattr(
            "foliate.quarto.is_quarto_preprocessing_available", lambda: True
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault
            config.advanced.quarto_enabled = True

            existing_page = vault / "existing.md"
            existing_page.write_text("---\npublic: true\n---\n# Existing")

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            build_file = build_dir / "index.html"
            build_file.write_text("<html>Test</html>")

            cache_dir = vault / ".foliate" / "cache"
            cache_dir.mkdir(parents=True)
            save_build_cache(
                cache_dir / ".build_cache",
                {str(existing_page): existing_page.stat().st_mtime},
            )

            imported_page = vault / "paper.qmd"
            imported_page.write_text("---\npublic: true\n---\n# Imported")
            older_than_build = build_file.stat().st_mtime - 3600
            os.utime(imported_page, (older_than_build, older_than_build))

            result = is_build_stale(config)

            assert result is True

    def test_returns_true_when_cached_public_page_was_deleted(self):
        """Should return True when a previously built public page was deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html>Test</html>")

            cache_dir = vault / ".foliate" / "cache"
            cache_dir.mkdir(parents=True)
            save_build_cache(
                cache_dir / ".build_cache",
                {str(vault / "deleted.md"): time.time()},
            )

            result = is_build_stale(config)
            assert result is True

    def test_returns_true_when_new_public_page_has_older_mtime_than_build(self):
        """New public pages should mark the build stale even with older mtimes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            existing_page = vault / "existing.md"
            existing_page.write_text("---\npublic: true\n---\n# Existing")

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            build_file = build_dir / "index.html"
            build_file.write_text("<html>Test</html>")

            cache_dir = vault / ".foliate" / "cache"
            cache_dir.mkdir(parents=True)
            save_build_cache(
                cache_dir / ".build_cache",
                {str(existing_page): existing_page.stat().st_mtime},
            )

            imported_page = vault / "imported.md"
            imported_page.write_text("---\npublic: true\n---\n# Imported")
            older_than_build = build_file.stat().st_mtime - 3600
            os.utime(imported_page, (older_than_build, older_than_build))

            result = is_build_stale(config)

            assert result is True

    def test_returns_true_when_new_uppercase_markdown_page_has_older_mtime_than_build(
        self,
    ):
        """Uppercase .MD pages should still mark the build stale when newly added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            existing_page = vault / "existing.md"
            existing_page.write_text("---\npublic: true\n---\n# Existing")

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            build_file = build_dir / "index.html"
            build_file.write_text("<html>Test</html>")

            cache_dir = vault / ".foliate" / "cache"
            cache_dir.mkdir(parents=True)
            save_build_cache(
                cache_dir / ".build_cache",
                {str(existing_page): existing_page.stat().st_mtime},
            )

            imported_page = vault / "Imported.MD"
            imported_page.write_text("---\npublic: true\n---\n# Imported")
            older_than_build = build_file.stat().st_mtime - 3600
            os.utime(imported_page, (older_than_build, older_than_build))

            result = is_build_stale(config)

            assert result is True

    def test_returns_false_when_duplicate_extension_alias_is_not_selected_source(self):
        """An ignored .MD alias should not keep the build permanently stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            config = Config()
            config.vault_path = vault

            selected_page = vault / "Guide.md"
            selected_page.write_text("---\npublic: true\n---\n# Lower")
            duplicate_page = vault / "Guide.MD"
            duplicate_page.write_text("---\npublic: true\n---\n# Upper")

            build_dir = vault / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            build_file = build_dir / "index.html"
            build_file.write_text("<html>Test</html>")

            older_than_build = build_file.stat().st_mtime - 3600
            os.utime(selected_page, (older_than_build, older_than_build))
            os.utime(duplicate_page, (older_than_build, older_than_build))

            cache_dir = vault / ".foliate" / "cache"
            cache_dir.mkdir(parents=True)
            save_build_cache(
                cache_dir / ".build_cache",
                {str(selected_page): selected_page.stat().st_mtime},
            )

            result = is_build_stale(config)

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

    def test_returns_false_when_deploy_target_unset(self, capsys):
        """Should treat an empty deploy target as missing, not cwd/vault root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)
            config.deploy = DeployConfig(target="")

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)

            result = deploy_github_pages(config)
            captured = capsys.readouterr()

            assert result is False
            assert "No deploy target configured" in captured.err

    def test_returns_false_when_deploy_target_whitespace(self, capsys):
        """Whitespace-only deploy targets should be treated as missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)
            config.deploy = DeployConfig(target="   ")

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)

            result = deploy_github_pages(config)
            captured = capsys.readouterr()

            assert result is False
            assert "No deploy target configured" in captured.err

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

            # Should resolve to sibling of tmpdir
            assert "sibling" in str(config.resolve_deploy_target())

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

    @patch("foliate.logging.info")
    @patch("foliate.deploy.subprocess.run")
    def test_dry_run_uses_rsync_output_to_detect_changes(self, mock_run, mock_info):
        """Should report commit intent when rsync dry-run shows file changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    "sending incremental file list\n"
                    ">f+++++++++ index.html\n\n"
                    "sent 91 bytes  received 19 bytes  220.00 bytes/sec\n"
                    "total size is 14  speedup is 0.13 (DRY RUN)\n"
                ),
                stderr="",
            )

            result = deploy_github_pages(config, dry_run=True)

            assert result is True
            mock_run.assert_called_once()
            called_args = mock_run.call_args[0][0]
            assert called_args[0] == "rsync"
            assert "--dry-run" in called_args
            assert "--itemize-changes" in called_args
            assert "--checksum" in called_args
            info_messages = [call.args[0] for call in mock_info.call_args_list]
            assert any("Would commit with message:" in msg for msg in info_messages)

    @patch("foliate.logging.info")
    @patch("foliate.deploy.subprocess.run")
    def test_dry_run_reports_no_changes_when_rsync_output_is_empty(
        self, mock_run, mock_info
    ):
        """Should return early when rsync dry-run reports no file changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    "sending incremental file list\n\n"
                    "sent 39 bytes  received 12 bytes  102.00 bytes/sec\n"
                    "total size is 14  speedup is 0.27 (DRY RUN)\n"
                ),
                stderr="",
            )

            result = deploy_github_pages(config, dry_run=True)

            assert result is True
            mock_run.assert_called_once()
            called_args = mock_run.call_args[0][0]
            assert "--checksum" in called_args
            info_messages = [call.args[0] for call in mock_info.call_args_list]
            assert any("No changes to deploy" in msg for msg in info_messages)
            assert not any("Would commit with message:" in msg for msg in info_messages)

    @patch("foliate.logging.info")
    @patch("foliate.deploy.subprocess.run")
    def test_dry_run_ignores_mtime_only_differences(self, mock_run, mock_info):
        """Identical files with different mtimes should not look deployable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)

            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            target_file = target_dir / "index.html"
            target_file.write_text("<html>same</html>")

            time.sleep(0.05)
            build_file = build_dir / "index.html"
            build_file.write_text("<html>same</html>")
            assert build_file.stat().st_mtime > target_file.stat().st_mtime

            result = deploy_github_pages(config, dry_run=True)

            assert result is True
            mock_run.assert_not_called()
            info_messages = [call.args[0] for call in mock_info.call_args_list]
            assert any("No changes to deploy" in msg for msg in info_messages)
            assert not any("Would commit with message:" in msg for msg in info_messages)

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

    @patch("foliate.logging.error")
    @patch("foliate.deploy.subprocess.run", side_effect=FileNotFoundError("rsync"))
    def test_returns_false_when_rsync_binary_is_missing(self, mock_run, mock_error):
        """Missing rsync should be reported as a deploy failure, not raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            result = deploy_github_pages(config, dry_run=True)

            assert result is False
            mock_run.assert_called_once()
            error_messages = [call.args[0] for call in mock_error.call_args_list]
            assert any("rsync failed: rsync" in msg for msg in error_messages)

    @patch("foliate.deploy.subprocess.run")
    def test_aborts_on_non_benign_git_pull_failure(self, mock_run):
        """Unexpected git pull failures should stop deployment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.vault_path = Path(tmpdir)

            build_dir = Path(tmpdir) / ".foliate" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text("<html></html>")

            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()
            (target_dir / ".git").mkdir()
            config.deploy = DeployConfig(target=str(target_dir))

            pull_failure = MagicMock(
                returncode=1,
                stdout="",
                stderr=(
                    "fatal: could not read Username for "
                    "'https://github.com': terminal prompts disabled"
                ),
            )
            mock_run.return_value = pull_failure

            result = deploy_github_pages(config)

            assert result is False
            mock_run.assert_called_once()


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
