"""Configuration loading and management for foliate."""

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def _load_dataclass(
    cls: type[T],
    data: dict,
    defaults: T,
    transforms: dict[str, callable] | None = None,
) -> T:
    """Load a dataclass from a dict with defaults and optional field transforms.

    Args:
        cls: The dataclass type to create
        data: Dict of values from config file
        defaults: Instance with default values
        transforms: Optional dict mapping field names to transform functions

    Returns:
        New instance of cls with values from data, falling back to defaults
    """
    transforms = transforms or {}
    kwargs = {}
    for f in fields(cls):
        value = data.get(f.name, getattr(defaults, f.name))
        if f.name in transforms:
            value = transforms[f.name](value)
        kwargs[f.name] = value
    return cls(**kwargs)


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
    home_page: str = "Home"  # Wiki page that shows recent pages list
    incremental: bool = True


@dataclass
class NavItem:
    """Navigation item configuration."""

    url: str
    label: str
    logo: str | None = None
    logo_alt: str | None = None


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
class DeployConfig:
    """Deployment configuration."""

    method: str = "github-pages"
    target: str = ""  # Path to GitHub Pages repo
    exclude: list[str] = field(
        default_factory=lambda: ["CNAME", ".gitignore", ".gitmodules", ".claude"]
    )


@dataclass
class Config:
    """Main configuration container."""

    site: SiteConfig = field(default_factory=SiteConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    nav: list[NavItem] = field(default_factory=list)
    footer: FooterConfig = field(default_factory=FooterConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    deploy: DeployConfig = field(default_factory=DeployConfig)

    # Computed paths (set after loading)
    vault_path: Path | None = None
    config_path: Path | None = None

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

        from .resources import expand_path

        # Load simple config sections using helper
        if "site" in data:
            config.site = _load_dataclass(SiteConfig, data["site"], config.site)

        if "build" in data:
            config.build = _load_dataclass(BuildConfig, data["build"], config.build)

        if "footer" in data:
            config.footer = _load_dataclass(FooterConfig, data["footer"], config.footer)

        if "advanced" in data:
            config.advanced = _load_dataclass(
                AdvancedConfig,
                data["advanced"],
                config.advanced,
                transforms={"quarto_python": expand_path},
            )

        if "deploy" in data:
            config.deploy = _load_dataclass(
                DeployConfig,
                data["deploy"],
                config.deploy,
                transforms={"target": expand_path},
            )

        # Load nav items (special handling for list of items)
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
            config.nav = [
                NavItem(url="/about/", label="About"),
                NavItem(url="/wiki/Home/", label="Wiki"),
            ]

        return config

    @classmethod
    def find_and_load(cls, start_path: Path | None = None) -> "Config":
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
    def find_config(start_path: Path) -> Path | None:
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

    def get_templates_dir(self) -> Path | None:
        """Get custom templates directory if it exists."""
        if self.vault_path:
            templates_dir = self.vault_path / ".foliate" / "templates"
            if templates_dir.exists():
                return templates_dir
        return None

    def get_static_dir(self) -> Path | None:
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
            "home_page": self.build.home_page,
        }
