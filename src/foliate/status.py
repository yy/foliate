"""Page status reporting for foliate.

Scans the vault and reports which pages would be built, deployed,
and whether they are new, modified, or unchanged since the last build.
"""

from dataclasses import dataclass
from pathlib import Path

from .build import get_content_info, get_output_path, is_path_ignored
from .cache import BUILD_CACHE_FILE, check_global_deps_changed, load_build_cache
from .config import Config
from .markdown_utils import parse_markdown_file


@dataclass
class PageStatus:
    """Status of a single page in the vault."""

    page_path: str
    source_file: Path
    base_url: str
    is_homepage_content: bool
    public: bool
    published: bool
    state: str  # "new", "modified", "unchanged"

    @property
    def output_url(self) -> str:
        """The URL this page will be served at."""
        return f"{self.base_url}{self.page_path}/"


@dataclass
class StatusReport:
    """Summary of all page statuses in the vault."""

    pages: list[PageStatus]

    @property
    def public_pages(self) -> list[PageStatus]:
        return [p for p in self.pages if p.public]

    @property
    def published_pages(self) -> list[PageStatus]:
        return [p for p in self.pages if p.public and p.published]

    @property
    def private_pages(self) -> list[PageStatus]:
        return [p for p in self.pages if not p.public]

    @property
    def new_pages(self) -> list[PageStatus]:
        return [p for p in self.pages if p.public and p.state == "new"]

    @property
    def modified_pages(self) -> list[PageStatus]:
        return [p for p in self.pages if p.public and p.state == "modified"]

    @property
    def unchanged_pages(self) -> list[PageStatus]:
        return [p for p in self.pages if p.public and p.state == "unchanged"]


def _get_page_state(
    md_file: Path,
    page_path: str,
    base_url: str,
    build_dir: Path,
    wiki_dir_name: str,
    build_cache: dict,
    force_rebuild_all: bool,
) -> str:
    """Determine whether a page is new, modified, or unchanged.

    Returns:
        "new", "modified", or "unchanged"
    """
    # Determine expected output file
    output_file = get_output_path(build_dir, page_path, base_url, wiki_dir_name)

    if not output_file.exists():
        return "new"

    # A global invalidation means existing pages will still rebuild.
    if force_rebuild_all:
        return "modified"

    # Check cache for modification
    cache_key = str(md_file)
    md_mtime = md_file.stat().st_mtime
    if cache_key in build_cache and build_cache[cache_key] >= md_mtime:
        return "unchanged"

    return "modified"


def scan_status(config: Config) -> StatusReport:
    """Scan the vault and produce a status report of all pages.

    Args:
        config: The foliate configuration

    Returns:
        StatusReport with the status of every markdown file
    """
    vault_path = config.vault_path
    if not vault_path or not vault_path.exists():
        return StatusReport(pages=[])

    ignored_folders = config.build.ignored_folders
    homepage_dir = config.build.homepage_dir
    wiki_base_url = config.base_urls["wiki"]
    wiki_dir_name = config.build.wiki_prefix.strip("/")

    build_dir = config.get_build_dir()
    cache_file = config.get_cache_dir() / BUILD_CACHE_FILE
    build_cache = load_build_cache(cache_file)
    force_rebuild_all = not config.build.incremental
    if (
        not force_rebuild_all
        and config.config_path
        and check_global_deps_changed(build_cache, config.config_path, vault_path)
    ):
        force_rebuild_all = True
        build_cache = {}

    pages: list[PageStatus] = []

    # Glob .md files, and .qmd files if Quarto is enabled
    globs = ["**/*.md"]
    if config.advanced.quarto_enabled:
        globs.append("**/*.qmd")
    source_files = sorted(f for pattern in globs for f in vault_path.glob(pattern))

    for md_file in source_files:
        if is_path_ignored(md_file, vault_path, ignored_folders):
            continue

        # Skip files inside .foliate/
        try:
            rel_path = md_file.relative_to(vault_path)
            if rel_path.parts and rel_path.parts[0] == ".foliate":
                continue
        except ValueError:
            continue

        page_path = rel_path.with_suffix("").as_posix()
        page_path, content_base_url, is_homepage = get_content_info(
            page_path, homepage_dir, wiki_base_url
        )

        meta, _ = parse_markdown_file(md_file)
        is_public = meta.get("public", False)
        is_published = meta.get("published", False)

        if is_public:
            state = _get_page_state(
                md_file,
                page_path,
                content_base_url,
                build_dir,
                wiki_dir_name,
                build_cache,
                force_rebuild_all,
            )
        else:
            state = "unchanged"  # not relevant for private pages

        pages.append(
            PageStatus(
                page_path=page_path,
                source_file=md_file,
                base_url=content_base_url,
                is_homepage_content=is_homepage,
                public=is_public,
                published=is_published,
                state=state,
            )
        )

    return StatusReport(pages=pages)


def format_status_report(report: StatusReport, verbose: bool = False) -> str:
    """Format a status report for display.

    Args:
        report: The status report to format
        verbose: If True, list all pages including unchanged ones

    Returns:
        Formatted string for terminal output
    """
    lines: list[str] = []

    new = report.new_pages
    modified = report.modified_pages
    unchanged = report.unchanged_pages
    private = report.private_pages

    if new:
        lines.append(f"New pages ({len(new)}):")
        for p in new:
            pub = " [published]" if p.published else ""
            lines.append(f"  + {p.page_path}{pub}")
        lines.append("")

    if modified:
        lines.append(f"Modified pages ({len(modified)}):")
        for p in modified:
            pub = " [published]" if p.published else ""
            lines.append(f"  ~ {p.page_path}{pub}")
        lines.append("")

    if verbose and unchanged:
        lines.append(f"Unchanged pages ({len(unchanged)}):")
        for p in unchanged:
            pub = " [published]" if p.published else ""
            lines.append(f"    {p.page_path}{pub}")
        lines.append("")

    # Summary line
    total_public = len(report.public_pages)
    total_published = len(report.published_pages)
    summary_parts = [
        f"{total_public} public",
        f"{total_published} published",
        f"{len(new)} new",
        f"{len(modified)} modified",
        f"{len(private)} private",
    ]
    lines.append("Summary: " + ", ".join(summary_parts))

    return "\n".join(lines)


def format_build_dry_run_report(
    report: StatusReport, force_rebuild: bool = False, verbose: bool = False
) -> str:
    """Format a dry-run preview of what `foliate build` would do."""
    lines: list[str] = ["Dry run: no files will be written."]

    if force_rebuild:
        build_candidates = report.public_pages
    else:
        build_candidates = report.new_pages + report.modified_pages

    lines.append(f"Would build ({len(build_candidates)}):")
    for p in build_candidates:
        pub = " [published]" if p.published else ""
        state = "forced" if force_rebuild else p.state
        lines.append(f"  + {p.page_path} ({state}){pub}")

    if verbose and not force_rebuild and report.unchanged_pages:
        lines.append("")
        lines.append(f"Cached/unchanged ({len(report.unchanged_pages)}):")
        for p in report.unchanged_pages:
            pub = " [published]" if p.published else ""
            lines.append(f"    {p.page_path}{pub}")

    if report.private_pages:
        lines.append("")
        lines.append(f"Private pages ({len(report.private_pages)}, skipped)")
        if verbose:
            for p in report.private_pages:
                pub = " [published]" if p.published else ""
                lines.append(f"  - {p.page_path}{pub}")

    lines.append("")
    lines.append(
        "Summary: "
        + ", ".join(
            [
                f"{len(report.public_pages)} public",
                f"{len(report.published_pages)} published",
                f"{len(build_candidates)} would build",
                f"{len(report.private_pages)} private",
            ]
        )
    )

    return "\n".join(lines)
