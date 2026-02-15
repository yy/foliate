"""Tests for resources module."""

import socket
import tempfile
from pathlib import Path

import pytest

from foliate.resources import (
    check_port_available,
    copy_package_files,
    expand_path,
    get_package_file_path,
    iter_package_files,
    read_package_bytes,
    read_package_text,
    start_dev_server,
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


class TestCheckPortAvailable:
    """Tests for check_port_available function."""

    def test_available_port_returns_true(self):
        """An unused port should be reported as available."""
        # Use port 0 to get a free port, then check that port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            _, free_port = s.getsockname()
        # Port is now free (socket closed)
        assert check_port_available(free_port) is True

    def test_occupied_port_returns_false(self):
        """A port in use should be reported as unavailable."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            s.listen(1)
            _, occupied_port = s.getsockname()
            assert check_port_available(occupied_port) is False


class TestStartDevServer:
    """Tests for start_dev_server function."""

    def test_raises_on_occupied_port(self, tmp_path):
        """Should raise OSError when port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            s.listen(1)
            _, occupied_port = s.getsockname()

            with pytest.raises(OSError, match="already in use"):
                start_dev_server(tmp_path, port=occupied_port, background=True)

    def test_background_server_starts_on_free_port(self, tmp_path):
        """Should successfully start a server on a free port."""
        # Get a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            _, free_port = s.getsockname()

        proc = start_dev_server(tmp_path, port=free_port, background=True)
        try:
            assert proc is not None
            assert proc.poll() is None  # Still running
        finally:
            proc.terminate()
            proc.wait()
