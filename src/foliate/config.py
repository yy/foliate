"""Configuration loading and management for foliate."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SiteConfig:
    """Site-level configuration."""

    name: str = "My Site"
    url: str = "https://example.com"
    author: str = ""
    default_og_image: str = "/assets/images/default-preview.png"


@dataclass
class BuildConfig:
    """Build-related configuration."""

    ignored_folders: list[str] = field(default_factory=lambda: ["_private"])
    home_redirect: str = "about"
    homepage_dir: str = "_homepage"
    wiki_prefix: str = "wiki"  # URL prefix for wiki content (e.g., /wiki/PageName/)
    incremental: bool = True


@dataclass
class NavItem:
    """Navigation item configuration."""

    url: str
    label: str
    logo: Optional[str] = None
    logo_alt: Optional[str] = None


@dataclass
class FooterConfig:
    """Footer configuration."""

    copyright_year: int = 2025
    author_name: str = ""
    author_link: str = "about/"


@dataclass
class AdvancedConfig:
    """Advanced configuration options."""

    quarto_enabled: bool = False
    quarto_python: str = ""


@dataclass
class Config:
    """Main configuration container."""

    site: SiteConfig = field(default_factory=SiteConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    nav: list[NavItem] = field(default_factory=list)
    footer: FooterConfig = field(default_factory=FooterConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)

    # Computed paths (set after loading)
    vault_path: Optional[Path] = None
    config_path: Optional[Path] = None

    @classmethod
    def load(cls, config_path: Path) -> "Config":
        """Load configuration from a TOML file.

        Args:
            config_path: Path to the config.toml file

        Returns:
            Loaded Config object with defaults merged
        """
        config = cls()
        config.config_path = config_path
        config.vault_path = config_path.parent.parent  # .foliate/config.toml -> vault

        if not config_path.exists():
            return config

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Load site config
        if "site" in data:
            site_data = data["site"]
            config.site = SiteConfig(
                name=site_data.get("name", config.site.name),
                url=site_data.get("url", config.site.url),
                author=site_data.get("author", config.site.author),
                default_og_image=site_data.get(
                    "default_og_image", config.site.default_og_image
                ),
            )

        # Load build config
        if "build" in data:
            build_data = data["build"]
            config.build = BuildConfig(
                ignored_folders=build_data.get(
                    "ignored_folders", config.build.ignored_folders
                ),
                home_redirect=build_data.get(
                    "home_redirect", config.build.home_redirect
                ),
                homepage_dir=build_data.get("homepage_dir", config.build.homepage_dir),
                wiki_prefix=build_data.get("wiki_prefix", config.build.wiki_prefix),
                incremental=build_data.get("incremental", config.build.incremental),
            )

        # Load nav items
        if "nav" in data and "items" in data["nav"]:
            config.nav = [
                NavItem(
                    url=item["url"],
                    label=item["label"],
                    logo=item.get("logo"),
                    logo_alt=item.get("logo_alt"),
                )
                for item in data["nav"]["items"]
            ]
        else:
            # Default nav items
            config.nav = [
                NavItem(url="/about/", label="About"),
                NavItem(url="/wiki/Home/", label="Wiki"),
            ]

        # Load footer config
        if "footer" in data:
            footer_data = data["footer"]
            config.footer = FooterConfig(
                copyright_year=footer_data.get(
                    "copyright_year", config.footer.copyright_year
                ),
                author_name=footer_data.get("author_name", config.footer.author_name),
                author_link=footer_data.get("author_link", config.footer.author_link),
            )

        # Load advanced config
        if "advanced" in data:
            import os

            adv_data = data["advanced"]
            quarto_python = adv_data.get("quarto_python", config.advanced.quarto_python)
            # Expand ~ in paths
            if quarto_python:
                quarto_python = os.path.expanduser(quarto_python)
            config.advanced = AdvancedConfig(
                quarto_enabled=adv_data.get(
                    "quarto_enabled", config.advanced.quarto_enabled
                ),
                quarto_python=quarto_python,
            )

        return config

    @classmethod
    def find_and_load(cls, start_path: Optional[Path] = None) -> "Config":
        """Find and load config from .foliate/config.toml.

        Searches from start_path up to filesystem root for .foliate/config.toml.

        Args:
            start_path: Directory to start searching from (default: cwd)

        Returns:
            Loaded Config object

        Raises:
            FileNotFoundError: If no .foliate/config.toml is found
        """
        if start_path is None:
            start_path = Path.cwd()

        config_path = cls.find_config(start_path)
        if config_path is None:
            raise FileNotFoundError(
                "No .foliate/config.toml found. Run 'foliate init' first."
            )

        return cls.load(config_path)

    @staticmethod
    def find_config(start_path: Path) -> Optional[Path]:
        """Find .foliate/config.toml starting from start_path.

        Args:
            start_path: Directory to start searching from

        Returns:
            Path to config.toml if found, None otherwise
        """
        current = start_path.resolve()

        while True:
            config_path = current / ".foliate" / "config.toml"
            if config_path.exists():
                return config_path

            parent = current.parent
            if parent == current:
                # Reached filesystem root
                return None
            current = parent

    def get_build_dir(self) -> Path:
        """Get the build output directory."""
        if self.vault_path:
            return self.vault_path / ".foliate" / "build"
        return Path.cwd() / ".foliate" / "build"

    def get_cache_dir(self) -> Path:
        """Get the cache directory."""
        if self.vault_path:
            return self.vault_path / ".foliate" / "cache"
        return Path.cwd() / ".foliate" / "cache"

    def get_templates_dir(self) -> Optional[Path]:
        """Get custom templates directory if it exists."""
        if self.vault_path:
            templates_dir = self.vault_path / ".foliate" / "templates"
            if templates_dir.exists():
                return templates_dir
        return None

    def get_static_dir(self) -> Optional[Path]:
        """Get custom static directory if it exists."""
        if self.vault_path:
            static_dir = self.vault_path / ".foliate" / "static"
            if static_dir.exists():
                return static_dir
        return None

    @property
    def base_urls(self) -> dict[str, str]:
        """Get base URLs for different content types."""
        wiki_prefix = self.build.wiki_prefix.strip("/")
        return {
            "wiki": f"/{wiki_prefix}/" if wiki_prefix else "/",
            "homepage": "/",
        }

    @property
    def default_base_url(self) -> str:
        """Get the default base URL for wiki content."""
        return self.base_urls["wiki"]

    def to_template_context(self) -> dict:
        """Convert config to a dict suitable for Jinja2 templates."""
        return {
            "site_name": self.site.name,
            "site_url": self.site.url,
            "default_og_image": self.site.default_og_image,
            "header_nav": [
                {
                    "url": item.url,
                    "label": item.label,
                    "logo": item.logo,
                    "logo_alt": item.logo_alt,
                }
                for item in self.nav
            ],
            "footer": {
                "copyright_year": self.footer.copyright_year,
                "author_name": self.footer.author_name or self.site.author,
                "author_link": self.footer.author_link,
            },
        }
