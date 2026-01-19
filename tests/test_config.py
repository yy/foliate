"""Tests for foliate configuration."""

from foliate.config import Config


class TestConfigLoading:
    """Tests for Config class."""

    def test_load_default_config(self, tmp_path):
        """Loading with no config file returns defaults."""
        config_path = tmp_path / ".foliate" / "config.toml"

        config = Config.load(config_path)

        assert config.site.name == "My Site"
        assert config.site.url == "https://example.com"
        assert config.build.ignored_folders == ["_private"]

    def test_load_custom_config(self, tmp_path):
        """Loading custom config merges with defaults."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Custom Site"
url = "https://custom.com"

[build]
ignored_folders = ["_private", "drafts"]
"""
        )

        config = Config.load(config_path)

        assert config.site.name == "Custom Site"
        assert config.site.url == "https://custom.com"
        assert config.build.ignored_folders == ["_private", "drafts"]

    def test_find_config_in_current_dir(self, tmp_path):
        """Finds config in current directory."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test'")

        found = Config.find_config(tmp_path)

        assert found == config_path

    def test_find_config_in_parent_dir(self, tmp_path):
        """Finds config in parent directory."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test'")

        child_dir = tmp_path / "subdir" / "nested"
        child_dir.mkdir(parents=True)

        found = Config.find_config(child_dir)

        assert found == config_path

    def test_find_config_not_found(self, tmp_path):
        """Returns None when config not found."""
        found = Config.find_config(tmp_path)

        assert found is None

    def test_config_paths(self, tmp_path):
        """Config correctly computes paths."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text("[site]\nname = 'Test'")

        config = Config.load(config_path)

        assert config.vault_path == tmp_path
        assert config.get_build_dir() == tmp_path / ".foliate" / "build"
        assert config.get_cache_dir() == tmp_path / ".foliate" / "cache"

    def test_wiki_prefix_default(self, tmp_path):
        """Default wiki_prefix is 'wiki'."""
        config_path = tmp_path / ".foliate" / "config.toml"

        config = Config.load(config_path)

        assert config.build.wiki_prefix == "wiki"
        assert config.base_urls["wiki"] == "/wiki/"

    def test_wiki_prefix_custom(self, tmp_path):
        """Custom wiki_prefix is respected."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[build]
wiki_prefix = "pages"
"""
        )

        config = Config.load(config_path)

        assert config.build.wiki_prefix == "pages"
        assert config.base_urls["wiki"] == "/pages/"

    def test_wiki_prefix_empty(self, tmp_path):
        """Empty wiki_prefix deploys to root."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[build]
wiki_prefix = ""
"""
        )

        config = Config.load(config_path)

        assert config.build.wiki_prefix == ""
        assert config.base_urls["wiki"] == "/"
