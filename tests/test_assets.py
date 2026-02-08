"""Tests for assets module."""

import tempfile
from pathlib import Path

from foliate.assets import copy_directory_incremental, copy_static_assets


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_copy_directory_incremental_removes_deleted_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        target_dir = Path(tmpdir) / "target"
        src_dir.mkdir()

        _write(src_dir / "a.txt", "a")
        _write(src_dir / "b.txt", "b")

        copy_directory_incremental(src_dir, target_dir, force_rebuild=True)

        assert (target_dir / "a.txt").exists()
        assert (target_dir / "b.txt").exists()

        (src_dir / "b.txt").unlink()

        copy_directory_incremental(src_dir, target_dir, force_rebuild=False)

        assert (target_dir / "a.txt").exists()
        assert not (target_dir / "b.txt").exists()


def test_copy_static_assets_preserves_bundled_defaults_with_user_static():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        user_static = vault / ".foliate" / "static"
        build_dir = vault / ".foliate" / "build"

        _write(user_static / "custom.css", "body { color: red; }")

        copy_static_assets(vault, build_dir, force_rebuild=False)

        static_dir = build_dir / "static"
        assert (static_dir / "custom.css").exists()
        assert (static_dir / "main.css").exists()


def test_copy_static_assets_removes_deleted_user_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        user_static = vault / ".foliate" / "static"
        build_dir = vault / ".foliate" / "build"

        _write(user_static / "custom.css", "body { color: red; }")
        copy_static_assets(vault, build_dir, force_rebuild=False)
        assert (build_dir / "static" / "custom.css").exists()

        (user_static / "custom.css").unlink()
        copy_static_assets(vault, build_dir, force_rebuild=False)

        assert not (build_dir / "static" / "custom.css").exists()
        assert (build_dir / "static" / "main.css").exists()
