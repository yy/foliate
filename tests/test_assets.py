"""Tests for assets module."""

import tempfile
from pathlib import Path

from foliate.assets import copy_directory_incremental


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
