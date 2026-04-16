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

    def test_resolve_deploy_target_returns_none_when_unset(self, tmp_path):
        """Missing deploy target resolves to None."""
        config_path = tmp_path / ".foliate" / "config.toml"

        config = Config.load(config_path)

        assert config.resolve_deploy_target() is None

    def test_resolve_deploy_target_returns_none_when_whitespace(self, tmp_path):
        """Whitespace-only deploy targets resolve to None."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[deploy]
target = "   "
"""
        )

        config = Config.load(config_path)

        assert config.resolve_deploy_target() is None

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

    def test_feed_config_defaults(self, tmp_path):
        """Default feed config has sensible defaults."""
        config_path = tmp_path / ".foliate" / "config.toml"

        config = Config.load(config_path)

        assert config.feed.enabled is True
        assert config.feed.title == ""
        assert config.feed.description == ""
        assert config.feed.language == "en"
        assert config.feed.items == 20
        assert config.feed.full_content is True
        assert config.feed.window == 30

    def test_feed_config_custom(self, tmp_path):
        """Custom feed config is loaded correctly."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[feed]
enabled = false
title = "My Custom Feed"
description = "A description"
language = "ko"
items = 10
full_content = false
window = 7
"""
        )

        config = Config.load(config_path)

        assert config.feed.enabled is False
        assert config.feed.title == "My Custom Feed"
        assert config.feed.description == "A description"
        assert config.feed.language == "ko"
        assert config.feed.items == 10
        assert config.feed.full_content is False
        assert config.feed.window == 7

    def test_expands_paths_in_advanced_and_deploy_sections(self, tmp_path, monkeypatch):
        """Path-valued config fields keep their expansion behavior."""
        monkeypatch.setenv("HOME", str(tmp_path))
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[advanced]
quarto_python = "~/bin/python3"

[deploy]
target = "~/site-deploy"
"""
        )

        config = Config.load(config_path)

        assert config.advanced.quarto_python == str(tmp_path / "bin" / "python3")
        assert config.deploy.target == str(tmp_path / "site-deploy")

    def test_resolve_deploy_target_relative_to_vault(self, tmp_path):
        """Relative deploy target paths resolve from the vault root."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[deploy]
target = "../site-deploy"
"""
        )

        config = Config.load(config_path)
        expected_target = (tmp_path / ".." / "site-deploy").resolve()

        assert config.resolve_deploy_target() == expected_target

    def test_nav_items_loaded(self, tmp_path):
        """Nav items preserve configured values."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[nav]
items = [
  { url = "/docs/", label = "Docs" },
  { url = "/about/", label = "About", logo = "/logo.svg", logo_alt = "Site logo" },
]
"""
        )

        config = Config.load(config_path)

        assert [item.label for item in config.nav] == ["Docs", "About"]
        assert config.nav[1].logo == "/logo.svg"
        assert config.nav[1].logo_alt == "Site logo"

    def test_default_nav_uses_custom_wiki_prefix(self, tmp_path):
        """Default nav should follow the configured wiki prefix."""
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

        assert [item.url for item in config.nav] == ["/about/", "/pages/Home/"]


class TestConfigValidation:
    """Tests for config validation and warnings."""

    def test_warns_on_unknown_key_in_site_section(self, tmp_path, capsys):
        """Unknown keys in config produce warnings."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test"
authro = "Typo User"
"""
        )

        Config.load(config_path)
        captured = capsys.readouterr()

        assert "authro" in captured.err
        assert "site" in captured.err

    def test_warns_on_unknown_key_in_build_section(self, tmp_path, capsys):
        """Unknown keys in build section produce warnings."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[build]
ignored_folder = ["_private"]
"""
        )

        Config.load(config_path)
        captured = capsys.readouterr()

        assert "ignored_folder" in captured.err
        assert "build" in captured.err

    def test_suggests_similar_key_for_typos(self, tmp_path, capsys):
        """Suggests correct key when typo is close."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test"
autor = "Typo"
"""
        )

        Config.load(config_path)
        captured = capsys.readouterr()

        assert "autor" in captured.err
        assert "author" in captured.err  # Suggestion

    def test_warns_on_unknown_top_level_section(self, tmp_path, capsys):
        """Unknown top-level sections produce warnings."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test"

[syte]
name = "Typo Section"
"""
        )

        Config.load(config_path)
        captured = capsys.readouterr()

        assert "syte" in captured.err

    def test_no_warnings_for_valid_config(self, tmp_path, capsys):
        """Valid config produces no warnings."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Valid Site"
url = "https://example.com"
author = "Valid Author"
"""
        )

        Config.load(config_path)
        captured = capsys.readouterr()

        assert captured.err == ""

    def test_warns_on_multiple_unknown_keys(self, tmp_path, capsys):
        """Multiple unknown keys each produce warnings."""
        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Test"
foo = "bar"
baz = "qux"
"""
        )

        Config.load(config_path)
        captured = capsys.readouterr()

        assert "foo" in captured.err
        assert "baz" in captured.err


class TestConfigErrorPaths:
    """Tests for error handling in config loading."""

    def test_find_and_load_raises_when_no_config_found(self, tmp_path):
        """Raises FileNotFoundError when no config file exists."""
        import pytest

        with pytest.raises(FileNotFoundError) as exc_info:
            Config.find_and_load(tmp_path)

        assert ".foliate/config.toml" in str(exc_info.value)
        assert "foliate init" in str(exc_info.value)

    def test_load_raises_on_invalid_toml_syntax(self, tmp_path):
        """Raises TOMLDecodeError for invalid TOML syntax."""
        import tomllib

        import pytest

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site
name = "Missing bracket"
"""
        )

        with pytest.raises(tomllib.TOMLDecodeError):
            Config.load(config_path)

    def test_load_raises_on_invalid_toml_value_syntax(self, tmp_path):
        """Raises TOMLDecodeError for invalid value syntax."""
        import tomllib

        import pytest

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[site]
name = "Unclosed string
"""
        )

        with pytest.raises(tomllib.TOMLDecodeError):
            Config.load(config_path)

    def test_load_raises_on_invalid_section_type(self, tmp_path):
        """Config sections must use table syntax."""
        import pytest

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text('site = "bad"\n')

        with pytest.raises(TypeError, match=r"\[site\].*must be a table"):
            Config.load(config_path)

    def test_load_raises_on_invalid_nav_items_type(self, tmp_path):
        """Nav items must be configured as a list."""
        import pytest

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[nav]
items = "bad"
"""
        )

        with pytest.raises(TypeError, match=r"\[nav\]\.items.*must be a list"):
            Config.load(config_path)

    def test_load_raises_on_missing_nav_item_url(self, tmp_path):
        """Nav items still require url and label keys."""
        import pytest

        config_dir = tmp_path / ".foliate"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text(
            """
[nav]
items = [
  { label = "Docs" },
]
"""
        )

        with pytest.raises(KeyError, match="url"):
            Config.load(config_path)
