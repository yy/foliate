"""Core build logic for foliate static site generator."""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

from .assets import copy_static_assets, copy_user_assets, robust_rmtree
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
    file_path: Path | None = None,
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
        "base_url": base_url,
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
    published_pages: list[dict] | None = None,
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

    # For home page, prepare recent pages
    home_page_name = config.build.home_page
    recent_pages = None
    if page["path"] == home_page_name and published_pages:
        filtered = [p for p in published_pages if p["path"] != home_page_name]
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


def iter_public_md_files(
    vault_path: Path,
    config: Config,
    single_page: str | None = None,
    on_skipped: Callable[[Path, str], None] | None = None,
):
    """Iterate over public markdown files in the vault.

    Yields:
        Tuples of (md_file, page_path, content_base_url, meta, markdown_content)
        for each public markdown file.
    """
    from .logging import debug

    ignored_folders = config.build.ignored_folders
    homepage_dir = config.build.homepage_dir
    wiki_base_url = config.base_urls["wiki"]

    for md_file in vault_path.glob("**/*.md"):
        if is_path_ignored(md_file, vault_path, ignored_folders):
            continue

        rel_path = md_file.relative_to(vault_path)
        page_path = rel_path.with_suffix("").as_posix()

        page_path, content_base_url, _ = get_content_info(
            page_path, homepage_dir, wiki_base_url
        )

        if single_page and page_path != single_page:
            continue

        meta, markdown_content = parse_markdown_file(md_file)

        # Check visibility
        if not meta.get("public", False):
            if single_page and page_path == single_page:
                debug(f"  Building single page (overriding privacy): {page_path}")
            else:
                if on_skipped:
                    on_skipped(md_file, page_path)
                continue

        yield md_file, page_path, content_base_url, meta, markdown_content


def process_single_md_file(
    md_file: Path,
    page_path: str,
    content_base_url: str,
    meta: dict,
    markdown_content: str,
    build_dir: Path,
    env: Environment,
    config: Config,
    build_cache: dict,
    force_rebuild: bool,
    incremental: bool,
) -> tuple[dict, bool]:
    """Process a single markdown file and return the page object.

    Returns:
        Tuple of (page_dict, was_rebuilt)
    """
    from .logging import debug

    wiki_dir = config.build.wiki_prefix.strip("/")

    # Determine output path
    if content_base_url == "/":
        output_file = build_dir / page_path / "index.html"
    else:
        output_file = build_dir / wiki_dir / page_path / "index.html"

    # Check if rebuild needed
    if incremental and not needs_rebuild(
        md_file, output_file, build_cache, force_rebuild
    ):
        debug(f"  Cached: {page_path}")
        page = create_page_object(
            page_path,
            meta,
            markdown_content,
            render_html=False,
            file_path=md_file,
            base_url=content_base_url,
        )
        return page, False

    # Rebuild
    debug(f"  Building: {page_path}")
    page = create_page_object(
        page_path,
        meta,
        markdown_content,
        render_html=True,
        file_path=md_file,
        base_url=content_base_url,
    )
    render_page_to_file(page, build_dir, env, config, None, content_base_url)
    return page, True


def process_markdown_files(
    vault_path: Path,
    build_dir: Path,
    env: Environment,
    config: Config,
    build_cache: dict,
    force_rebuild: bool,
    incremental: bool,
    single_page: str | None = None,
) -> tuple[list[dict], list[dict], dict, dict]:
    """Process all markdown files and return page data and statistics."""
    public_pages = []
    published_pages = []
    new_build_cache = {}
    stats = {"skipped_count": 0, "rebuilt_count": 0, "cached_count": 0}

    def _track_skipped(_md_file: Path, _page_path: str) -> None:
        stats["skipped_count"] += 1

    for md_file, page_path, base_url, meta, content in iter_public_md_files(
        vault_path, config, single_page, on_skipped=_track_skipped
    ):
        page, was_rebuilt = process_single_md_file(
            md_file,
            page_path,
            base_url,
            meta,
            content,
            build_dir,
            env,
            config,
            build_cache,
            force_rebuild,
            incremental,
        )

        new_build_cache[str(md_file)] = md_file.stat().st_mtime
        public_pages.append(page)

        if was_rebuilt:
            stats["rebuilt_count"] += 1
        else:
            stats["cached_count"] += 1

        if meta.get("published", False):
            published_pages.append(page)

    return public_pages, published_pages, new_build_cache, stats


def render_home_page(
    public_pages: list[dict],
    published_pages: list[dict],
    build_dir: Path,
    env: Environment,
    config: Config,
) -> None:
    """Re-render the home page with the recent pages list."""
    from .logging import debug

    home_page_name = config.build.home_page
    home_page = next((p for p in public_pages if p["path"] == home_page_name), None)
    if not home_page:
        return

    home_base_url = home_page.get("base_url", config.base_urls["wiki"])

    debug(f"  Re-rendering {home_page_name} page with recent pages...")

    if not home_page.get("html"):
        home_page["html"] = render_markdown(home_page["body"], home_base_url)

    render_page_to_file(
        home_page, build_dir, env, config, published_pages, home_base_url
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
    (build_dir / "sitemap.txt").write_text("\n".join(sitemap_lines), encoding="utf-8")


def generate_site_files(
    build_dir: Path,
    env: Environment,
    config: Config,
    published_pages: list[dict],
    public_pages: list[dict],
) -> None:
    """Generate site-wide files: home redirect, wiki redirect, search.json, sitemap."""
    wiki_base_url = config.base_urls["wiki"]
    wiki_dir_name = config.build.wiki_prefix.strip("/")

    # Generate home page redirect
    home_url = f"/{config.build.home_redirect.lower()}/"
    redirect_template = env.get_template("index.html")
    home_html = redirect_template.render(
        redirect_url=home_url,
        redirect_title=config.build.home_redirect.title(),
    )
    (build_dir / "index.html").write_text(home_html, encoding="utf-8")

    # Generate wiki root redirect (only if wiki_prefix is set)
    if wiki_dir_name:
        wiki_home_url = f"/{wiki_dir_name}/{config.build.home_page}/"
        wiki_redirect_html = redirect_template.render(
            redirect_url=wiki_home_url,
            redirect_title=config.build.home_page,
        )
        wiki_dir = build_dir / wiki_dir_name
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "index.html").write_text(wiki_redirect_html, encoding="utf-8")

    generate_search_index(build_dir, public_pages, wiki_base_url, wiki_dir_name)
    generate_sitemap(build_dir, public_pages, wiki_base_url)


# ---------------------------------------------------------------------------
# Build orchestration
# ---------------------------------------------------------------------------


def _setup_build_environment(
    config: Config, force_rebuild: bool, incremental: bool
) -> tuple[Path, Path, dict, Environment, bool]:
    """Setup build directories, load cache, and create Jinja environment.

    Returns:
        Tuple of (build_dir, cache_file, build_cache, jinja_env, force_rebuild)
        Note: force_rebuild may be updated if config/templates changed
    """
    from .cache import check_global_deps_changed
    from .logging import debug

    vault_path = config.vault_path
    build_dir = config.get_build_dir()
    cache_dir = config.get_cache_dir()
    cache_file = cache_dir / BUILD_CACHE_FILE

    # Load build cache first to check global deps
    build_cache = {}
    if incremental and not force_rebuild:
        build_cache = load_build_cache(cache_file)

        # Check if config or templates changed - if so, force rebuild
        if (
            vault_path
            and config.config_path
            and check_global_deps_changed(build_cache, config.config_path, vault_path)
        ):
            debug("Config or templates changed, forcing full rebuild...")
            force_rebuild = True
            build_cache = {}

    # Setup build directories
    if force_rebuild and build_dir.exists():
        debug("Force rebuild: Cleaning build directory...")
        robust_rmtree(build_dir)

    build_dir.mkdir(parents=True, exist_ok=True)

    # Setup Jinja2 environment with template loader
    env = Environment(loader=get_template_loader(vault_path))  # type: ignore[arg-type]

    return build_dir, cache_file, build_cache, env, force_rebuild


def _print_build_summary(
    stats: dict,
    public_pages: list[dict],
    published_pages: list[dict],
    build_dir: Path,
    incremental: bool,
    force_rebuild: bool,
) -> None:
    """Print build summary."""
    from .logging import debug, info

    # Verbose output goes to debug level
    debug("\nBuild complete!")
    if incremental and not force_rebuild:
        debug(f"  - {stats['rebuilt_count']} pages rebuilt")
        debug(f"  - {stats['cached_count']} pages cached (unchanged)")
        debug(f"  - {stats['skipped_count']} private pages skipped")
    else:
        debug(f"  - {len(public_pages)} public pages generated")
        debug(f"  - {stats['skipped_count']} private pages skipped")
    debug(f"  - {len(published_pages)} published pages (visible in listings)")
    debug(f"  - Output directory: {build_dir.absolute()}")

    # Concise summary always shown
    if incremental and not force_rebuild:
        rebuilt = stats["rebuilt_count"]
        cached = stats["cached_count"]
        summary = f"Done: {rebuilt} rebuilt, {cached} cached, {len(published_pages)} published"
    else:
        summary = f"Done: {len(public_pages)} public, {len(published_pages)} published"
    info(summary)


def build(
    config: Config,
    force_rebuild: bool = False,
    incremental: bool | None = None,
    single_page: str | None = None,
) -> int:
    """Build static site from markdown pages.

    Args:
        config: Configuration object
        force_rebuild: Force rebuild all pages regardless of modification time
        incremental: Enable incremental builds (default from config)
        single_page: Build only the specified page

    Returns:
        Number of public pages built
    """
    from .logging import debug, error, info

    if incremental is None:
        incremental = config.build.incremental

    vault_path = config.vault_path
    if not vault_path:
        error("No vault path configured")
        return 0

    if not vault_path.exists():
        error(f"Vault directory '{vault_path}' does not exist")
        return 0

    # Preprocess Quarto files (.qmd -> .md)
    if config.advanced.quarto_enabled:
        from .quarto import preprocess_quarto

        debug("Preprocessing Quarto files...")
        preprocess_quarto(config, force=force_rebuild)

    # Setup build environment (force_rebuild may be updated if config/templates changed)
    build_dir, cache_file, build_cache, env, force_rebuild = _setup_build_environment(
        config, force_rebuild, incremental
    )

    # Copy assets
    copy_static_assets(vault_path, build_dir, force_rebuild)
    copy_user_assets(vault_path, build_dir, force_rebuild)

    # Print build status
    timestamp = datetime.now().strftime("%H:%M:%S")
    info(f"[{timestamp}] Building...")
    mode_text = "Force rebuilding" if force_rebuild else "Building"
    debug(f"{mode_text} static site...")

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
    )

    # Re-render Home page with recent pages
    if not single_page:
        render_home_page(public_pages, published_pages, build_dir, env, config)

    # Generate site-wide files only for full builds.
    if not single_page:
        generate_site_files(build_dir, env, config, published_pages, public_pages)

    # Generate Atom feed
    if config.feed.enabled and not single_page:
        from .feed import generate_feed

        debug("Generating Atom feed...")
        generate_feed(published_pages, config, env, build_dir)

    # Post-process HTML to sanitize private links
    from .postprocess import postprocess_links

    debug("Post-processing HTML files...")
    postprocess_links(config, public_pages, single_page=single_page)

    # Save build cache (including global deps like config and templates)
    if incremental and config.config_path:
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
    )

    return len(public_pages)
