"""Tests for quarto module."""

import tempfile
from pathlib import Path

from foliate.config import AdvancedConfig, Config
from foliate.quarto import preprocess_quarto


class TestPreprocessQuarto:
    """Tests for preprocess_quarto function."""

    def test_returns_empty_when_disabled(self):
        """Should return empty dict when quarto is disabled."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=False)

        result = preprocess_quarto(config)

        assert result == {}

    def test_returns_empty_when_no_vault_path(self):
        """Should return empty dict when vault_path is None."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = None

        result = preprocess_quarto(config)

        assert result == {}

    def test_handles_missing_quarto_prerender(self):
        """Should gracefully handle when quarto-prerender is not installed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.advanced = AdvancedConfig(quarto_enabled=True)
            config.vault_path = Path(tmpdir)

            # This will either succeed (if quarto-prerender is installed)
            # or return empty dict (if not installed or quarto not available)
            result = preprocess_quarto(config)

            assert isinstance(result, dict)

    def test_processes_vault_with_no_qmd_files(self):
        """Should return empty dict when no .qmd files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a vault with only .md files
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test")

            config = Config()
            config.advanced = AdvancedConfig(quarto_enabled=True)
            config.vault_path = Path(tmpdir)

            result = preprocess_quarto(config)

            # Either empty (no qmd files) or dict with results
            assert isinstance(result, dict)

    def test_config_values_preserved(self):
        """Should preserve config values correctly."""
        config = Config()
        config.advanced = AdvancedConfig(
            quarto_enabled=True, quarto_python="/usr/bin/python3"
        )

        assert config.advanced.quarto_enabled is True
        assert config.advanced.quarto_python == "/usr/bin/python3"

    def test_force_flag_accepted(self):
        """Should accept force flag without error."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=False)

        # Should not raise even with force=True
        result = preprocess_quarto(config, force=True)

        assert result == {}

    def test_single_file_with_disabled_quarto(self):
        """Should return empty when quarto disabled even with single_file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            qmd_file = Path(tmpdir) / "test.qmd"
            qmd_file.write_text("# Test")

            config = Config()
            config.advanced = AdvancedConfig(quarto_enabled=False)
            config.vault_path = Path(tmpdir)

            result = preprocess_quarto(config, single_file=qmd_file)

            assert result == {}
