"""Configuration loading and management for foliate."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TypeVar

from .markdown_utils import slugify_path

T = TypeVar("T")


def _find_similar(key: str, valid_keys: set[str], threshold: float = 0.6) -> str | None:
    """Find a similar key from valid_keys using Levenshtein ratio.

    Args:
        key: The unknown key to match
        valid_keys: Set of valid key names
        threshold: Minimum similarity ratio (0-1) to suggest

    Returns:
        Most similar key if above threshold, None otherwise
    """

    def levenshtein_ratio(s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        m, n = len(s1), len(s2)
        if m == 0 or n == 0:
            return 0.0

        # Create distance matrix
        d = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            d[i][0] = i
        for j in range(n + 1):
            d[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)

        max_len = max(m, n)
        return 1.0 - (d[m][n] / max_len)

    best_match = None
    best_ratio = 0.0

    for valid in valid_keys:
        ratio = levenshtein_ratio(key.lower(), valid.lower())
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = valid

    return best_match if best_ratio >= threshold else None


def _warn_unknown_keys(
    data: dict[str, object],
    valid_keys: set[str],
    section: str,
    config_path: Path | None = None,
) -> None:
    """Warn about unknown keys in a config section.

    Args:
        data: Dict of config values
        valid_keys: Set of valid field names for this section
        section: Section name for error messages
        config_path: Path to config file for error messages
    """
    from .logging import warning

    unknown_keys = set(data.keys()) - valid_keys
    if not unknown_keys:
        return

    for key in sorted(unknown_keys):
        location = f" in {config_path}" if config_path else ""
        msg = f"Unknown config key '{key}' in [{section}]{location}"

        similar = _find_similar(key, valid_keys)
        if similar:
            msg += f". Did you mean '{similar}'?"

        warning(msg)


def _load_dataclass(
    cls: type[T],
    data: dict[str, object],
    defaults: T,
    transforms: dict[str, Callable[[object], object]] | None = None,
    section: str = "",
    config_path: Path | None = None,
) -> T:
    """Load a dataclass from a dict with defaults and optional field transforms.

    Args:
        cls: The dataclass type to create
        data: Dict of values from config file
        defaults: Instance with default values
        transforms: Optional dict mapping field names to transform functions
        section: Section name for validation warnings
        config_path: Path to config file for validation warnings

    Returns:
        New instance of cls with values from data, falling back to defaults
    """
    from dataclasses import fields as dc_fields

    transforms = transforms or {}
    kwargs: dict[str, object] = {}
    valid_keys = {f.name for f in dc_fields(cls)}  # type: ignore[arg-type]

    # Warn about unknown keys
    _warn_unknown_keys(data, valid_keys, section, config_path)

    for field_name in valid_keys:
        value = data.get(field_name, getattr(defaults, field_name))
        if field_name in transforms:
            value = transforms[field_name](value)
        kwargs[field_name] = value
    return cls(**kwargs)


def _require_section_dict(
    data: dict[str, object], section: str, config_path: Path
) -> dict[str, object] | None:
    """Return a config section if present, otherwise validate its shape."""
    section_data = data.get(section)
    if section_data is None:
        return None
    if not isinstance(section_data, dict):
        raise TypeError(
            f"Config section [{section}] in {config_path} must be a table, "
            f"got {type(section_data).__name__}"
        )
    return section_data


def _default_nav_items(
    wiki_base_url: str = "/wiki/",
    home_page: str = "Home",
    slugify_urls: bool = False,
) -> list["NavItem"]:
    wiki_home = slugify_path(home_page) if slugify_urls else home_page
    return [
        NavItem(url="/about/", label="About"),
        NavItem(url=f"{wiki_base_url}{wiki_home}/", label="Wiki"),
    ]


def _load_nav_items(
    data: dict[str, object],
    config_path: Path,
    wiki_base_url: str = "/wiki/",
    home_page: str = "Home",
    slugify_urls: bool = False,
) -> list["NavItem"]:
    """Load and validate nav items."""
    nav_data = _require_section_dict(data, "nav", config_path)
    if nav_data is None:
        return _default_nav_items(wiki_base_url, home_page, slugify_urls)

    items = nav_data.get("items")
    if items is None:
        return _default_nav_items(wiki_base_url, home_page, slugify_urls)
    if not isinstance(items, list):
        raise TypeError(
            f"Config section [nav].items in {config_path} must be a list, "
            f"got {type(items).__name__}"
        )

    nav_items: list[NavItem] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(
                f"Config section [nav].items[{index}] in {config_path} must be a "
                f"table, got {type(item).__name__}"
            )
        if "url" not in item:
            raise KeyError(f"Missing required key 'url' in [nav].items[{index}]")
        if "label" not in item:
            raise KeyError(f"Missing required key 'label' in [nav].items[{index}]")

        url = item["url"]
        label = item["label"]
        logo = item.get("logo")
        logo_alt = item.get("logo_alt")
        if not isinstance(url, str):
            raise TypeError(
                f"Config section [nav].items[{index}].url in {config_path} must be "
                f"a string, got {type(url).__name__}"
            )
        if not isinstance(label, str):
            raise TypeError(
                f"Config section [nav].items[{index}].label in {config_path} must be "
                f"a string, got {type(label).__name__}"
            )
        if logo is not None and not isinstance(logo, str):
            raise TypeError(
                f"Config section [nav].items[{index}].logo in {config_path} must be "
                f"a string, got {type(logo).__name__}"
            )
        if logo_alt is not None and not isinstance(logo_alt, str):
            raise TypeError(
                f"Config section [nav].items[{index}].logo_alt in {config_path} "
                f"must be a string, got {type(logo_alt).__name__}"
            )

        nav_items.append(NavItem(url=url, label=label, logo=logo, logo_alt=logo_alt))

    return nav_items


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
    nl2br: bool = False  # Convert single newlines to <br> (Obsidian-style)
    slugify_urls: bool = False  # Replace spaces with hyphens in URLs


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
class FeedConfig:
    """Feed generation configuration."""

    enabled: bool = True
    title: str = ""
    description: str = ""
    language: str = "en"
    items: int = 20
    full_content: bool = True
    window: int = 30


@dataclass
class Config:
    """Main configuration container."""

    site: SiteConfig = field(default_factory=SiteConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    nav: list[NavItem] = field(default_factory=list)
    footer: FooterConfig = field(default_factory=FooterConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    deploy: DeployConfig = field(default_factory=DeployConfig)
    feed: FeedConfig = field(default_factory=FeedConfig)

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

        with config_path.open("rb") as f:
            data: dict[str, object] = tomllib.load(f)

        from .resources import expand_path

        def _expand_path_value(value: object) -> object:
            if isinstance(value, str):
                return expand_path(value)
            return value

        # Validate top-level sections
        valid_sections = {
            "site",
            "build",
            "nav",
            "footer",
            "advanced",
            "deploy",
            "feed",
            "visibility",
        }
        _warn_unknown_keys(data, valid_sections, "top-level", config_path)

        # Load simple config sections using helper
        site_data = _require_section_dict(data, "site", config_path)
        if site_data is not None:
            config.site = _load_dataclass(
                SiteConfig,
                site_data,
                config.site,
                section="site",
                config_path=config_path,
            )

        build_data = _require_section_dict(data, "build", config_path)
        if build_data is not None:
            config.build = _load_dataclass(
                BuildConfig,
                build_data,
                config.build,
                section="build",
                config_path=config_path,
            )

        footer_data = _require_section_dict(data, "footer", config_path)
        if footer_data is not None:
            config.footer = _load_dataclass(
                FooterConfig,
                footer_data,
                config.footer,
                section="footer",
                config_path=config_path,
            )

        advanced_data = _require_section_dict(data, "advanced", config_path)
        if advanced_data is not None:
            config.advanced = _load_dataclass(
                AdvancedConfig,
                advanced_data,
                config.advanced,
                transforms={"quarto_python": _expand_path_value},
                section="advanced",
                config_path=config_path,
            )

        deploy_data = _require_section_dict(data, "deploy", config_path)
        if deploy_data is not None:
            config.deploy = _load_dataclass(
                DeployConfig,
                deploy_data,
                config.deploy,
                transforms={"target": _expand_path_value},
                section="deploy",
                config_path=config_path,
            )

        feed_data = _require_section_dict(data, "feed", config_path)
        if feed_data is not None:
            config.feed = _load_dataclass(
                FeedConfig,
                feed_data,
                config.feed,
                section="feed",
                config_path=config_path,
            )

        config.nav = _load_nav_items(
            data,
            config_path,
            config.base_urls["wiki"],
            config.build.home_page,
            config.build.slugify_urls,
        )

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

    def to_template_context(self) -> dict[str, object]:
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
            "feed_enabled": self.feed.enabled,
            "feed_title": self.feed.title or self.site.name,
        }
