"""Tests for quarto module."""

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import Mock

from foliate.config import AdvancedConfig, Config
from foliate.quarto import (
    _clean_rendered_markdown,
    _unescape_outside_code,
    get_buildable_content_suffixes,
    preprocess_quarto,
)


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

    def test_single_file_missing_is_skipped(self, monkeypatch, tmp_path):
        """Missing single-file QMD paths should be ignored without rendering."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        qmd_file = tmp_path / "paper.qmd"
        generated_md = tmp_path / "paper.md"
        generated_md.write_text("# Existing generated markdown")

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        fake_module.process_all = lambda **_kwargs: {}
        render_qmd = Mock(name="render_qmd")
        fake_module.render_qmd = render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        result = preprocess_quarto(config, single_file=qmd_file)

        assert result == {}
        render_qmd.assert_not_called()

    def test_bulk_mode_processes_uppercase_qmd(self, monkeypatch, tmp_path):
        """Bulk preprocessing should discover uppercase .QMD files."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        qmd_file = tmp_path / "paper.QMD"
        qmd_file.write_text("# Test")
        generated_md = tmp_path / "paper.md"
        cached_md = tmp_path / ".foliate" / "cache" / "quarto" / "rendered" / "paper.md"

        def fake_render_qmd(**_kwargs):
            generated_md.write_text("---\ntitle: Paper\n---\n# Rendered\n")
            return generated_md

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        render_qmd = Mock(name="render_qmd", side_effect=fake_render_qmd)
        fake_module.render_qmd = render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        result = preprocess_quarto(config)

        assert result == {str(qmd_file): str(cached_md)}
        assert cached_md.exists()
        assert not generated_md.exists()
        render_qmd.assert_called_once()
        assert render_qmd.call_args.kwargs["qmd_file"] == qmd_file

    def test_bulk_mode_prefers_lowercase_qmd_when_case_variants_exist(
        self, monkeypatch, tmp_path
    ):
        """Lowercase .qmd should keep precedence when both case variants exist."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        lower_qmd = tmp_path / "paper.qmd"
        lower_qmd.write_text("# Lower")
        upper_qmd = tmp_path / "paper.QMD"
        upper_qmd.write_text("# Upper")
        generated_md = tmp_path / "paper.md"
        cached_md = tmp_path / ".foliate" / "cache" / "quarto" / "rendered" / "paper.md"

        def fake_render_qmd(**_kwargs):
            generated_md.write_text("---\ntitle: Paper\n---\n# Rendered\n")
            return generated_md

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        render_qmd = Mock(name="render_qmd", side_effect=fake_render_qmd)
        fake_module.render_qmd = render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        result = preprocess_quarto(config)

        assert result == {str(lower_qmd): str(cached_md)}
        assert cached_md.exists()
        render_qmd.assert_called_once()
        assert render_qmd.call_args.kwargs["qmd_file"] == lower_qmd

    def test_single_file_writes_cache_and_private_preview(self, monkeypatch, tmp_path):
        """Single-file preprocessing writes cached markdown and Obsidian preview."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        qmd_file = tmp_path / "notes" / "paper.qmd"
        qmd_file.parent.mkdir()
        qmd_file.write_text("---\ntitle: Paper\n---\n[[Link]]\n")
        generated_md = qmd_file.with_suffix(".md")

        def fake_render_qmd(**_kwargs):
            generated_md.write_text(
                "---\ntitle: Paper\n---\n# Paper\ny\n2026-01-01\n\n\\[\\[Link\\]\\]\n",
                encoding="utf-8",
            )
            return generated_md

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        fake_module.render_qmd = fake_render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        result = preprocess_quarto(config, single_file=qmd_file)

        cached_md = (
            tmp_path
            / ".foliate"
            / "cache"
            / "quarto"
            / "rendered"
            / "notes"
            / "paper.md"
        )
        preview_md = tmp_path / "_private" / "quarto-preview" / "notes" / "paper.md"

        assert result == {str(qmd_file): str(cached_md)}
        assert cached_md.read_text(encoding="utf-8") == (
            "---\ntitle: Paper\n---\n\n[[Link]]\n"
        )
        assert preview_md.read_text(encoding="utf-8") == (
            "---\ntitle: Paper\n---\n\n"
            "<!-- GENERATED FROM notes/paper.qmd; DO NOT EDIT -->\n\n"
            "[[Link]]\n"
        )
        assert not generated_md.exists()

    def test_existing_cache_recreates_missing_preview_without_render(
        self, monkeypatch, tmp_path
    ):
        """Missing preview markdown should be recreated from existing cache."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        qmd_file = tmp_path / "paper.qmd"
        qmd_file.write_text("# Source", encoding="utf-8")

        cached_md = tmp_path / ".foliate" / "cache" / "quarto" / "rendered" / "paper.md"
        cached_md.parent.mkdir(parents=True)
        cached_md.write_text("---\ntitle: Paper\n---\nRendered\n", encoding="utf-8")
        preview_md = tmp_path / "_private" / "quarto-preview" / "paper.md"

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        render_qmd = Mock(name="render_qmd")
        fake_module.render_qmd = render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        result = preprocess_quarto(config, single_file=qmd_file)

        assert result == {str(qmd_file): str(cached_md)}
        assert preview_md.read_text(encoding="utf-8") == (
            "---\ntitle: Paper\n---\n\n"
            "<!-- GENERATED FROM paper.qmd; DO NOT EDIT -->\n\n"
            "Rendered\n"
        )
        render_qmd.assert_not_called()

    def test_orphaned_sibling_backup_is_recovered(self, monkeypatch, tmp_path):
        """A backup stranded by a crashed prior run is restored on next run."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        qmd_file = tmp_path / "paper.qmd"
        qmd_file.write_text("# Source", encoding="utf-8")

        cached_md = tmp_path / ".foliate" / "cache" / "quarto" / "rendered" / "paper.md"
        cached_md.parent.mkdir(parents=True)
        cached_md.write_text("---\ntitle: Paper\n---\nRendered\n", encoding="utf-8")

        # Simulate a crash that left the user's hand-authored sibling stranded
        # as a backup with no live sibling present.
        sibling_backup = tmp_path / "paper.md.foliate-bak"
        sibling_backup.write_text("USER CONTENT", encoding="utf-8")

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        render_qmd = Mock(name="render_qmd")
        fake_module.render_qmd = render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        preprocess_quarto(config, single_file=qmd_file)

        sibling_md = tmp_path / "paper.md"
        assert sibling_md.read_text(encoding="utf-8") == "USER CONTENT"
        assert not sibling_backup.exists()
        render_qmd.assert_not_called()

    def test_failed_render_preserves_existing_assets(self, monkeypatch, tmp_path):
        """A render that fails restores the previous per-document assets."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)
        config.vault_path = tmp_path

        qmd_file = tmp_path / "paper.qmd"
        qmd_file.write_text("# Source", encoding="utf-8")

        asset_dir = tmp_path / "assets" / "quarto" / "paper"
        asset_dir.mkdir(parents=True)
        (asset_dir / "old.png").write_text("old", encoding="utf-8")

        def fake_render_qmd(**_kwargs):
            # Partially write new output, then fail.
            asset_dir.mkdir(parents=True, exist_ok=True)
            (asset_dir / "new.png").write_text("new", encoding="utf-8")
            return None

        fake_module = types.ModuleType("quarto_prerender")
        fake_module.is_quarto_available = lambda: True
        fake_module.render_qmd = fake_render_qmd
        monkeypatch.setitem(sys.modules, "quarto_prerender", fake_module)

        result = preprocess_quarto(config, single_file=qmd_file)

        assert result == {}
        assert (asset_dir / "old.png").read_text(encoding="utf-8") == "old"
        assert not (asset_dir / "new.png").exists()
        assert not (tmp_path / "assets" / "quarto" / "paper.foliate-bak").exists()


class TestCleanRenderedMarkdown:
    """Tests for rendered-markdown cleaning helpers."""

    def test_unescape_preserves_fenced_code_blocks(self):
        """Wikilink/pipe un-escaping must not touch fenced code content."""
        text = (
            "Body \\[\\[Wiki\\]\\] and a \\| pipe.\n"
            "\n"
            "```\n"
            "code \\[\\[raw\\]\\] \\| literal\n"
            "```\n"
        )

        result = _unescape_outside_code(text)

        assert "Body [[Wiki]] and a | pipe." in result
        assert "code \\[\\[raw\\]\\] \\| literal" in result

    def test_generated_title_strip_keeps_following_prose(self):
        """A heading matching the stem must not swallow a real paragraph."""
        text = (
            "---\ntitle: T\n---\n"
            "# doc\n"
            "This is a real sentence that should survive cleaning.\n"
        )

        cleaned = _clean_rendered_markdown(text, Path("doc.qmd"))

        assert cleaned == (
            "---\ntitle: T\n---\n\n"
            "This is a real sentence that should survive cleaning.\n"
        )


class TestGetBuildableContentSuffixes:
    """Tests for selecting buildable content suffixes."""

    def test_returns_markdown_only_when_quarto_disabled(self):
        """Disabled Quarto should never expose qmd sources to callers."""
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=False)

        assert get_buildable_content_suffixes(config) == {".md"}

    def test_returns_markdown_only_when_quarto_unavailable(self, monkeypatch):
        """Unavailable preprocessing should exclude qmd-only sources."""
        monkeypatch.setattr(
            "foliate.quarto.is_quarto_preprocessing_available", lambda: False
        )
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)

        assert get_buildable_content_suffixes(config) == {".md"}

    def test_includes_qmd_when_quarto_available(self, monkeypatch):
        """Available preprocessing should include qmd sources."""
        monkeypatch.setattr(
            "foliate.quarto.is_quarto_preprocessing_available", lambda: True
        )
        config = Config()
        config.advanced = AdvancedConfig(quarto_enabled=True)

        assert get_buildable_content_suffixes(config) == {".md", ".qmd"}
