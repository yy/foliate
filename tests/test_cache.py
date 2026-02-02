"""Tests for foliate build cache."""

from foliate import cache as build_cache


class TestNeedsRebuild:
    """Tests for needs_rebuild() function."""

    def test_force_always_rebuilds(self, tmp_path):
        """Force flag always returns True."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")
        output_file = tmp_path / "output.html"
        output_file.write_text("output")

        assert build_cache.needs_rebuild(md_file, output_file, {}, force=True) is True

    def test_missing_output_rebuilds(self, tmp_path):
        """Missing output file returns True."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")
        output_file = tmp_path / "nonexistent.html"

        assert build_cache.needs_rebuild(md_file, output_file, {}) is True

    def test_cached_file_no_rebuild(self, tmp_path):
        """File in cache with same mtime returns False."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")
        output_file = tmp_path / "output.html"
        output_file.write_text("output")

        cache = {str(md_file): md_file.stat().st_mtime}

        assert build_cache.needs_rebuild(md_file, output_file, cache) is False

    def test_stale_cache_rebuilds(self, tmp_path):
        """File newer than cache entry returns True."""
        md_file = tmp_path / "test.md"
        md_file.write_text("content")
        output_file = tmp_path / "output.html"
        output_file.write_text("output")

        cache = {str(md_file): md_file.stat().st_mtime - 100}

        assert build_cache.needs_rebuild(md_file, output_file, cache) is True


class TestBuildCache:
    """Tests for load_build_cache() and save_build_cache()."""

    def test_load_nonexistent_cache(self, tmp_path):
        """Loading nonexistent cache returns empty dict."""
        cache_file = tmp_path / ".build_cache"

        result = build_cache.load_build_cache(cache_file)

        assert result == {}

    def test_save_and_load_cache(self, tmp_path):
        """Can save and load cache data."""
        cache_file = tmp_path / ".build_cache"
        cache_data = {"file1.md": 12345.0, "file2.md": 67890.0}

        build_cache.save_build_cache(cache_file, cache_data)
        result = build_cache.load_build_cache(cache_file)

        assert result == cache_data

    def test_load_corrupted_cache(self, tmp_path):
        """Loading corrupted cache returns empty dict."""
        cache_file = tmp_path / ".build_cache"
        cache_file.write_text("not valid json data")

        result = build_cache.load_build_cache(cache_file)

        assert result == {}

    def test_load_legacy_pickle_cache(self, tmp_path):
        """Loading legacy pickle cache returns empty dict."""
        import pickle

        cache_file = tmp_path / ".build_cache"
        cache_file.write_bytes(pickle.dumps({"file1.md": 12345.0}))

        result = build_cache.load_build_cache(cache_file)

        assert result == {}
