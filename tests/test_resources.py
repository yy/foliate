"""Tests for resources module."""

import tempfile
from pathlib import Path

from foliate.resources import (
    copy_package_files,
    expand_path,
    get_package_file_path,
    iter_package_files,
    read_package_bytes,
    read_package_text,
)


class TestExpandPath:
    """Tests for expand_path function."""

    def test_expands_tilde(self):
        result = expand_path("~/test")
        assert "~" not in result
        assert result.endswith("/test")

    def test_handles_empty_string(self):
        assert expand_path("") == ""

    def test_handles_none_like(self):
        # Empty string is falsy
        assert expand_path("") == ""

    def test_preserves_absolute_paths(self):
        result = expand_path("/absolute/path")
        assert result == "/absolute/path"

    def test_preserves_relative_paths(self):
        result = expand_path("relative/path")
        assert result == "relative/path"


class TestReadPackageText:
    """Tests for read_package_text function."""

    def test_reads_existing_file(self):
        result = read_package_text("foliate.defaults", "config.toml")
        assert result is not None
        assert "[site]" in result

    def test_returns_none_for_missing_file(self):
        result = read_package_text("foliate.defaults", "nonexistent.txt")
        assert result is None

    def test_returns_none_for_missing_package(self):
        result = read_package_text("nonexistent.package", "file.txt")
        assert result is None


class TestReadPackageBytes:
    """Tests for read_package_bytes function."""

    def test_reads_existing_file(self):
        result = read_package_bytes("foliate.defaults.static", "main.css")
        assert result is not None
        assert isinstance(result, bytes)

    def test_returns_none_for_missing_file(self):
        result = read_package_bytes("foliate.defaults", "nonexistent.bin")
        assert result is None


class TestIterPackageFiles:
    """Tests for iter_package_files function."""

    def test_iterates_templates(self):
        files = list(iter_package_files("foliate.defaults.templates", suffix=".html"))
        assert len(files) > 0
        assert all(name.endswith(".html") for name, _ in files)

    def test_excludes_python_files(self):
        files = list(iter_package_files("foliate.defaults"))
        names = [name for name, _ in files]
        assert not any(name.endswith(".py") for name in names)

    def test_handles_missing_package(self):
        files = list(iter_package_files("nonexistent.package"))
        assert files == []


class TestCopyPackageFiles:
    """Tests for copy_package_files function."""

    def test_copies_files_to_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates"
            created = copy_package_files(
                "foliate.defaults.templates", target, suffix=".html"
            )
            assert len(created) > 0
            assert (target / "layout.html").exists()
            assert (target / "page.html").exists()

    def test_does_not_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates"
            target.mkdir()
            (target / "layout.html").write_text("custom content")

            copy_package_files(
                "foliate.defaults.templates", target, suffix=".html", force=False
            )

            assert (target / "layout.html").read_text() == "custom content"

    def test_overwrites_with_force(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates"
            target.mkdir()
            (target / "layout.html").write_text("custom content")

            copy_package_files(
                "foliate.defaults.templates", target, suffix=".html", force=True
            )

            assert (target / "layout.html").read_text() != "custom content"

    def test_creates_target_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "nested" / "templates"
            copy_package_files("foliate.defaults.templates", target)
            assert target.exists()


class TestGetPackageFilePath:
    """Tests for get_package_file_path function."""

    def test_returns_path_for_existing_file(self):
        result = get_package_file_path("foliate.defaults", "config.toml")
        assert result is not None
        assert result.exists()

    def test_returns_none_for_missing_file(self):
        result = get_package_file_path("foliate.defaults", "nonexistent.txt")
        assert result is None
