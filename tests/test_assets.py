"""Tests for assets module."""

import shutil
import tempfile
from pathlib import Path

from foliate.assets import (
    copy_directory_incremental,
    copy_static_assets,
    copy_user_assets,
    get_user_static_dir,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_get_user_static_dir_returns_standard_project_path(tmp_path):
    assert get_user_static_dir(tmp_path) == tmp_path / ".foliate" / "static"


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


def test_copy_directory_incremental_initial_copy_respects_extension_filter():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        target_dir = Path(tmpdir) / "target"
        src_dir.mkdir()

        _write(src_dir / "allowed.txt", "allowed")
        _write(src_dir / "ignored.tmp", "ignored")
        _write(src_dir / "nested" / "kept.txt", "nested")

        copy_directory_incremental(
            src_dir,
            target_dir,
            force_rebuild=True,
            filter_extensions={".txt"},
        )

        assert (target_dir / "allowed.txt").exists()
        assert (target_dir / "nested" / "kept.txt").exists()
        assert not (target_dir / "ignored.tmp").exists()


def test_copy_directory_incremental_removes_unsupported_target_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        target_dir = Path(tmpdir) / "target"
        src_dir.mkdir()
        target_dir.mkdir()

        _write(src_dir / "allowed.txt", "allowed")
        _write(target_dir / "allowed.txt", "allowed")
        _write(target_dir / "leftover.tmp", "leftover")

        copy_directory_incremental(
            src_dir,
            target_dir,
            force_rebuild=False,
            filter_extensions={".txt"},
        )

        assert (target_dir / "allowed.txt").exists()
        assert not (target_dir / "leftover.tmp").exists()


def test_copy_directory_incremental_replaces_conflicting_empty_target_file(tmp_path):
    src_dir = tmp_path / "src"
    target_dir = tmp_path / "target"
    src_dir.mkdir()
    target_dir.write_text("not a directory", encoding="utf-8")

    copy_directory_incremental(src_dir, target_dir, force_rebuild=False)

    assert target_dir.is_dir()


def test_copy_directory_incremental_tolerates_target_created_during_copy(
    monkeypatch, tmp_path
):
    src_dir = tmp_path / "src"
    target_dir = tmp_path / "target"
    src_dir.mkdir()
    _write(src_dir / "image.png", "image")
    real_copytree = shutil.copytree

    def copytree_after_target_appears(src, dst, **kwargs):
        Path(dst).mkdir(parents=True)
        return real_copytree(src, dst, **kwargs)

    monkeypatch.setattr("foliate.assets.shutil.copytree", copytree_after_target_appears)

    copy_directory_incremental(src_dir, target_dir, force_rebuild=False)

    assert (target_dir / "image.png").read_text(encoding="utf-8") == "image"


def test_copy_directory_incremental_skips_matching_tree(monkeypatch, tmp_path):
    src_dir = tmp_path / "src"
    target_dir = tmp_path / "target"
    src_dir.mkdir()
    target_dir.mkdir()

    _write(src_dir / "allowed.txt", "allowed")
    _write(target_dir / "allowed.txt", "allowed")

    copy_calls: list[tuple[Path, Path, set[str] | None]] = []
    rmtree_calls: list[Path] = []

    monkeypatch.setattr(
        "foliate.assets._copy_directory",
        lambda src, target, extensions=None: copy_calls.append(
            (src, target, extensions)
        ),
    )
    monkeypatch.setattr(
        "foliate.assets.robust_rmtree",
        lambda path: rmtree_calls.append(path),
    )

    copy_directory_incremental(
        src_dir,
        target_dir,
        force_rebuild=False,
        filter_extensions={".txt"},
    )

    assert copy_calls == []
    assert rmtree_calls == []


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


def test_copy_static_assets_ignores_non_directory_user_static_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        foliate_dir = vault / ".foliate"
        build_dir = foliate_dir / "build"

        foliate_dir.mkdir()
        (foliate_dir / "static").write_text("not a directory", encoding="utf-8")

        copy_static_assets(vault, build_dir, force_rebuild=False)

        static_dir = build_dir / "static"
        assert static_dir.is_dir()
        assert (static_dir / "main.css").exists()


def test_copy_user_assets_ignores_non_directory_assets_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        build_dir = vault / ".foliate" / "build"
        build_dir.mkdir(parents=True)

        (vault / "assets").write_text("not a directory", encoding="utf-8")

        copy_user_assets(vault, build_dir, force_rebuild=False)

        assert not (build_dir / "assets").exists()


def test_copy_user_assets_skips_excluded_folders():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        build_dir = vault / ".foliate" / "build"

        _write(vault / "assets" / "images" / "kept.png", "kept")
        _write(vault / "assets" / "drafts" / "draft.png", "draft")
        _write(vault / "assets" / "images" / "drafts" / "nested-draft.png", "draft")

        copy_user_assets(
            vault, build_dir, force_rebuild=True, excluded_folders=["drafts"]
        )

        assert (build_dir / "assets" / "images" / "kept.png").exists()
        assert not (build_dir / "assets" / "drafts").exists()
        assert not (build_dir / "assets" / "images" / "drafts").exists()


def test_copy_user_assets_removes_previously_deployed_excluded_folder():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        build_dir = vault / ".foliate" / "build"

        _write(vault / "assets" / "images" / "kept.png", "kept")
        _write(vault / "assets" / "drafts" / "draft.png", "draft")

        # Deployed before the exclusion existed: drafts are in the target.
        copy_user_assets(vault, build_dir, force_rebuild=True)
        assert (build_dir / "assets" / "drafts" / "draft.png").exists()

        # Incremental copy with the exclusion active cleans them up.
        copy_user_assets(
            vault, build_dir, force_rebuild=False, excluded_folders=["drafts"]
        )
        assert (build_dir / "assets" / "images" / "kept.png").exists()
        assert not (build_dir / "assets" / "drafts").exists()


def test_copy_user_assets_excluded_changes_do_not_trigger_refresh():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        build_dir = vault / ".foliate" / "build"

        _write(vault / "assets" / "images" / "kept.png", "kept")

        copy_user_assets(
            vault, build_dir, force_rebuild=True, excluded_folders=["drafts"]
        )
        target_file = build_dir / "assets" / "images" / "kept.png"
        mtime_before = target_file.stat().st_mtime

        # New/changed draft files must not cause a target rebuild.
        _write(vault / "assets" / "drafts" / "new-draft.png", "draft")
        copy_user_assets(
            vault, build_dir, force_rebuild=False, excluded_folders=["drafts"]
        )

        assert target_file.stat().st_mtime == mtime_before
        assert not (build_dir / "assets" / "drafts").exists()
