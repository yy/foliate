"""Core build logic for foliate static site generator."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment

from .assets import copy_static_assets, copy_user_assets
from .cache import (
    BUILD_CACHE_FILE,
    load_build_cache,
    needs_rebuild,
    save_build_cache,
)
from .config import Config
from .markdown_utils import (
    extract_description,
    extract_first_image,
    parse_markdown_file,
    render_markdown,
)
from .templates import get_template_loader

# Re-export cache functions for backward compatibility


def is_path_ignored(
    file_path: Path, base_dir: Path, ignored_folders: list[str]
) -> bool:
    """Check if file is in an ignored folder.

    Args:
        file_path: Path to the file to check
        base_dir: Base directory for computing relative path
        ignored_folders: List of folder names to ignore

    Returns:
        True if the file is in an ignored folder
    """
    if not ignored_folders:
        return False
    try:
        rel_path = file_path.relative_to(base_dir)
    except ValueError:
        return False
    # Check directories only (not the filename)
    for part in rel_path.parts[:-1]:
        if part in ignored_folders:
            return True
    return False


def get_content_info(
    page_path: str, homepage_dir: str, wiki_base_url: str = "/wiki/"
) -> tuple[str, str, bool]:
    """Determine content type and adjust page path for homepage content.

    Args:
        page_path: Original page path
        homepage_dir: Homepage directory name (e.g., "_homepage")
        wiki_base_url: Base URL for wiki content (e.g., "/wiki/")

    Returns:
        Tuple of (adjusted_page_path, base_url, is_homepage_content)
    """
    is_homepage = page_path.startswith(homepage_dir + "/")
    base_url = "/" if is_homepage else wiki_base_url
    if is_homepage:
        page_path = page_path[len(homepage_dir) + 1 :]
    return page_path, base_url, is_homepage


def create_page_object(
    page_path: str,
    meta: dict,
    markdown_content: str,
    render_html: bool = True,
    file_path: Optional[Path] = None,
    base_url: str = "/wiki/",
) -> dict:
    """Create a page object with all necessary fields."""
    page_url = f"{base_url}{page_path}/"

    description = meta.get("description") or extract_description(markdown_content)

    image = meta.get("image") or extract_first_image(markdown_content)
    if image and not image.startswith(("/", "http://", "https://")):
        image = f"/assets/{image}"

    page = {
        "path": page_path,
        "title": meta.get("title", page_path),
        "meta": meta,
        "body": markdown_content,
        "html": render_markdown(markdown_content, base_url) if render_html else "",
        "published": meta.get("published"),
        "tags": meta.get("tags", []),
        "date": meta.get("date"),
        "url": page_url,
        "description": description,
        "image": image,
    }

    if file_path:
        mtime = file_path.stat().st_mtime
        page["file_modified"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        page["file_mtime"] = mtime

    return page


def render_page_to_file(
    page: dict,
    build_dir: Path,
    env: Environment,
    config: Config,
    published_pages: Optional[list[dict]] = None,
    base_url: str = "/wiki/",
) -> None:
    """Render a page object to HTML file."""
    wiki_dir_name = config.build.wiki_prefix.strip("/")

    # Determine output directory
    if base_url == "/":
        page_dir = build_dir / page["path"]
    else:
        page_dir = build_dir / wiki_dir_name / page["path"]

    page_dir.mkdir(parents=True, exist_ok=True)

    # Choose template
    template_name = "page.html"

    # For Home page, prepare recent pages
    recent_pages = None
    if page["path"] == "Home" and published_pages:
        filtered = [p for p in published_pages if p["path"] != "Home"]
        recent_pages = sorted(
            filtered, key=lambda x: x.get("file_mtime", 0), reverse=True
        )[:20]

    template = env.get_template(template_name)

    # Get template context from config
    ctx = config.to_template_context()

    html = template.render(
        page=page,
        title=page["title"],
        content=page["html"],
        is_static=True,
        recent_pages=recent_pages,
        current_page=page,
        base_url=base_url,
        **ctx,
    )

    (page_dir / "index.html").write_text(html, encoding="utf-8")


def process_markdown_files(
    vault_path: Path,
    build_dir: Path,
    env: Environment,
    config: Config,
    build_cache: dict,
    force_rebuild: bool,
    incremental: bool,
    single_page: Optional[str] = None,
    verbose: bool = False,
) -> tuple[list[dict], list[dict], dict, dict]:
    """Process all markdown files and return page data and statistics."""
    public_pages = []
    published_pages = []
    new_build_cache = {}

    stats = {
        "skipped_count": 0,
        "rebuilt_count": 0,
        "cached_count": 0,
    }

    ignored_folders = config.build.ignored_folders
    homepage_dir = config.build.homepage_dir
    wiki_base_url = config.base_urls["wiki"]
    wiki_dir = config.build.wiki_prefix.strip("/")

    all_md_files = list(vault_path.glob("**/*.md"))

    for md_file in all_md_files:
        if is_path_ignored(md_file, vault_path, ignored_folders):
            continue

        rel_path = md_file.relative_to(vault_path)
        page_path = str(rel_path.with_suffix(""))

        page_path, content_base_url, is_homepage_content = get_content_info(
            page_path, homepage_dir, wiki_base_url
        )

        if single_page and page_path != single_page:
            continue

        meta, markdown_content = parse_markdown_file(md_file)

        if not meta.get("public", False):
            if single_page and page_path == single_page:
                if verbose:
                    print(f"  Building single page (overriding privacy): {page_path}")
            else:
                if verbose:
                    print(f"  Skipping private: {page_path}")
                stats["skipped_count"] += 1
                continue

        if content_base_url == "/":
            output_file = build_dir / page_path / "index.html"
        else:
            output_file = build_dir / wiki_dir / page_path / "index.html"

        if incremental and not needs_rebuild(
            md_file, output_file, build_cache, force_rebuild
        ):
            stats["cached_count"] += 1
            if verbose:
                print(f"  Cached: {page_path}")

            page = create_page_object(
                page_path,
                meta,
                markdown_content,
                render_html=False,
                file_path=md_file,
                base_url=content_base_url,
            )
            new_build_cache[str(md_file)] = md_file.stat().st_mtime
        else:
            stats["rebuilt_count"] += 1
            if verbose:
                print(f"  Building: {page_path}")

            page = create_page_object(
                page_path,
                meta,
                markdown_content,
                render_html=True,
                file_path=md_file,
                base_url=content_base_url,
            )
            render_page_to_file(page, build_dir, env, config, None, content_base_url)
            new_build_cache[str(md_file)] = md_file.stat().st_mtime

        public_pages.append(page)
        if meta.get("published", False):
            published_pages.append(page)

    return public_pages, published_pages, new_build_cache, stats


def render_home_page(
    public_pages: list[dict],
    published_pages: list[dict],
    build_dir: Path,
    env: Environment,
    config: Config,
    verbose: bool = False,
) -> None:
    """Re-render the Home page with the recent pages list."""
    home_page = next((p for p in public_pages if p["path"] == "Home"), None)
    if not home_page:
        return

    wiki_base_url = config.base_urls["wiki"]

    if verbose:
        print("  Re-rendering Home page with recent pages...")

    if not home_page.get("html"):
        home_page["html"] = render_markdown(home_page["body"], wiki_base_url)

    render_page_to_file(
        home_page, build_dir, env, config, published_pages, wiki_base_url
    )


def generate_search_index(
    build_dir: Path,
    public_pages: list[dict],
    base_url: str = "/wiki/",
    wiki_dir_name: str = "wiki",
) -> None:
    """Generate search.json for client-side search."""
    search_data = []
    for page in public_pages:
        content_preview = page["body"][:500] if page["body"] else ""

        published = page["meta"].get("published", "")
        if hasattr(published, "isoformat"):
            published = published.isoformat()

        search_data.append(
            {
                "title": page["title"],
                "path": page["path"],
                "url": f"{base_url}{page['path']}/",
                "content": content_preview,
                "published": str(published) if published else "",
                "tags": page.get("tags", []),
            }
        )

    wiki_dir = build_dir / wiki_dir_name
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "search.json").write_text(
        json.dumps(search_data, indent=2), encoding="utf-8"
    )


def generate_sitemap(
    build_dir: Path, public_pages: list[dict], base_url: str = "/wiki/"
) -> None:
    """Generate sitemap.txt with all public page URLs."""
    sitemap_lines = [f"{base_url}{page['path']}/" for page in public_pages]
    (build_dir / "sitemap.txt").write_text("\n".join(sitemap_lines))


def generate_site_files(
    build_dir: Path,
    env: Environment,
    config: Config,
    published_pages: list[dict],
    public_pages: list[dict],
) -> None:
    """Generate site-wide files: home redirect, search.json, sitemap."""
    wiki_base_url = config.base_urls["wiki"]
    wiki_dir_name = config.build.wiki_prefix.strip("/")

    # Generate home page redirect
    home_url = f"/{config.build.home_redirect.lower()}/"
    redirect_template = env.get_template("index.html")
    home_html = redirect_template.render(
        redirect_url=home_url,
        redirect_title=config.build.home_redirect.title(),
    )
    (build_dir / "index.html").write_text(home_html)

    generate_search_index(build_dir, public_pages, wiki_base_url, wiki_dir_name)
    generate_sitemap(build_dir, public_pages, wiki_base_url)


# ---------------------------------------------------------------------------
# Build orchestration
# ---------------------------------------------------------------------------


def _setup_build_environment(
    config: Config, force_rebuild: bool, incremental: bool, verbose: bool
) -> tuple[Path, Path, dict, Environment, bool]:
    """Setup build directories, load cache, and create Jinja environment.

    Returns:
        Tuple of (build_dir, cache_file, build_cache, jinja_env, force_rebuild)
        Note: force_rebuild may be updated if config/templates changed
    """
    from .cache import check_global_deps_changed

    vault_path = config.vault_path
    build_dir = config.get_build_dir()
    cache_dir = config.get_cache_dir()
    cache_file = cache_dir / BUILD_CACHE_FILE

    # Load build cache first to check global deps
    build_cache = {}
    if incremental and not force_rebuild:
        build_cache = load_build_cache(cache_file)

        # Check if config or templates changed - if so, force rebuild
        if check_global_deps_changed(build_cache, config.config_path, vault_path):
            if verbose:
                print("Config or templates changed, forcing full rebuild...")
            force_rebuild = True
            build_cache = {}

    # Setup build directories
    if force_rebuild and build_dir.exists():
        if verbose:
            print("Force rebuild: Cleaning build directory...")
        shutil.rmtree(build_dir)

    build_dir.mkdir(parents=True, exist_ok=True)

    # Setup Jinja2 environment with template loader
    env = Environment(loader=get_template_loader(vault_path))

    return build_dir, cache_file, build_cache, env, force_rebuild


def _print_build_summary(
    stats: dict,
    public_pages: list[dict],
    published_pages: list[dict],
    build_dir: Path,
    incremental: bool,
    force_rebuild: bool,
    verbose: bool,
) -> None:
    """Print build summary."""
    if verbose:
        print("\nBuild complete!")
        if incremental and not force_rebuild:
            print(f"  - {stats['rebuilt_count']} pages rebuilt")
            print(f"  - {stats['cached_count']} pages cached (unchanged)")
            print(f"  - {stats['skipped_count']} private pages skipped")
        else:
            print(f"  - {len(public_pages)} public pages generated")
            print(f"  - {stats['skipped_count']} private pages skipped")
        print(f"  - {len(published_pages)} published pages (visible in listings)")
        print(f"  - Output directory: {build_dir.absolute()}")
    else:
        if incremental and not force_rebuild:
            summary = f"Done: {stats['rebuilt_count']} rebuilt, {stats['cached_count']} cached, {len(published_pages)} published"
        else:
            summary = (
                f"Done: {len(public_pages)} public, {len(published_pages)} published"
            )
        print(summary)


def build(
    config: Config,
    force_rebuild: bool = False,
    incremental: Optional[bool] = None,
    single_page: Optional[str] = None,
    verbose: bool = False,
) -> int:
    """Build static site from markdown pages.

    Args:
        config: Configuration object
        force_rebuild: Force rebuild all pages regardless of modification time
        incremental: Enable incremental builds (default from config)
        single_page: Build only the specified page
        verbose: Enable verbose output

    Returns:
        Number of public pages built
    """
    if incremental is None:
        incremental = config.build.incremental

    vault_path = config.vault_path
    if not vault_path:
        print("Error: No vault path configured")
        return 0

    if not vault_path.exists():
        print(f"Error: Vault directory '{vault_path}' does not exist")
        return 0

    # Setup build environment (force_rebuild may be updated if config/templates changed)
    build_dir, cache_file, build_cache, env, force_rebuild = _setup_build_environment(
        config, force_rebuild, incremental, verbose
    )

    # Copy assets
    copy_static_assets(vault_path, build_dir, force_rebuild)
    copy_user_assets(vault_path, build_dir, force_rebuild)

    # Print build status
    if not verbose:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Building...")
    else:
        mode_text = "Force rebuilding" if force_rebuild else "Building"
        print(f"{mode_text} static site...")

    # Process markdown files
    public_pages, published_pages, new_build_cache, stats = process_markdown_files(
        vault_path,
        build_dir,
        env,
        config,
        build_cache,
        force_rebuild,
        incremental,
        single_page,
        verbose,
    )

    # Re-render Home page with recent pages
    if not single_page:
        render_home_page(public_pages, published_pages, build_dir, env, config, verbose)

    # Generate site files
    generate_site_files(build_dir, env, config, published_pages, public_pages)

    # Save build cache (including global deps like config and templates)
    if incremental:
        from .cache import update_global_deps_cache

        update_global_deps_cache(new_build_cache, config.config_path, vault_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        save_build_cache(cache_file, new_build_cache)

    # Print summary
    _print_build_summary(
        stats,
        public_pages,
        published_pages,
        build_dir,
        incremental,
        force_rebuild,
        verbose,
    )

    return len(public_pages)
