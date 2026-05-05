"""Page status reporting for foliate.

Scans the vault and reports which pages would be built, deployed,
and whether they are new, modified, or unchanged since the last build.
"""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .build import (
    ContentRoute,
    ContentRouteCollisionError,
    get_output_path,
    select_content_sources,
)
from .config import Config
from .markdown_utils import parse_markdown_file
from .quarto import get_buildable_content_suffixes


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
    def route(self) -> ContentRoute:
        """Logical route for this page status."""
        return ContentRoute.from_page_path(self.page_path, self.base_url)

    @property
    def output_url(self) -> str:
        """The URL this page will be served at."""
        return self.route.public_url()


@dataclass
class StatusReport:
    """Summary of all page statuses in the vault."""

    pages: list[PageStatus]
    deploy_target: str | None = None  # path to deploy target, if comparing against it

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


def _resolve_deploy_dir(config: Config) -> Path | None:
    """Resolve the deploy target directory, if configured and exists."""
    target = config.resolve_deploy_target()
    if target is None:
        return None
    if target.exists():
        return target
    return None


def _get_last_deploy_time(deploy_dir: Path) -> float | None:
    """Get the timestamp of the last git commit in the deploy directory.

    Returns None when git metadata is unavailable (e.g., non-git deploy target).
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=deploy_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (OSError, ValueError):
        pass
    return None


def _get_page_state(
    md_file: Path,
    page_path: str,
    base_url: str,
    build_dir: Path,
    wiki_dir_name: str,
    deploy_dir: Path | None = None,
    last_deploy_time: float | None = None,
) -> str:
    """Determine whether a page is new, modified, or unchanged.

    When deploy_dir is provided, compares against the deploy target to show
    what would change on the next deployment. Otherwise, compares against
    the local build directory.

    Returns:
        "new", "modified", or "unchanged"
    """
    if deploy_dir is not None:
        deploy_file = get_output_path(deploy_dir, page_path, base_url, wiki_dir_name)
        if not deploy_file.exists():
            return "new"

        source_mtime = md_file.stat().st_mtime
        if last_deploy_time is not None:
            baseline = last_deploy_time
        else:
            # Deploy target may exist without git history; compare file mtimes.
            baseline = deploy_file.stat().st_mtime

        if source_mtime > baseline:
            return "modified"
        return "unchanged"

    # Fallback: compare against build directory
    output_file = get_output_path(build_dir, page_path, base_url, wiki_dir_name)
    if not output_file.exists():
        return "new"
    if md_file.stat().st_mtime > output_file.stat().st_mtime:
        return "modified"
    return "unchanged"


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

    wiki_dir_name = config.build.wiki_prefix.strip("/")

    build_dir = config.get_build_dir()
    deploy_dir = _resolve_deploy_dir(config)
    last_deploy_time = _get_last_deploy_time(deploy_dir) if deploy_dir else None

    pages: list[PageStatus] = []
    try:
        selected_sources = select_content_sources(
            vault_path,
            config,
            get_buildable_content_suffixes(config),
            duplicate_label="source files",
        )
    except ContentRouteCollisionError as exc:
        from .logging import error

        error(str(exc))
        return StatusReport(pages=[])

    for source in selected_sources:
        meta, _ = parse_markdown_file(source.source_file)
        is_public = bool(meta.get("public", False))
        is_published = bool(meta.get("published", False))

        if is_public:
            state = _get_page_state(
                source.source_file,
                source.page_path,
                source.base_url,
                build_dir,
                wiki_dir_name,
                deploy_dir=deploy_dir,
                last_deploy_time=last_deploy_time,
            )
        else:
            state = "unchanged"  # not relevant for private pages

        pages.append(
            PageStatus(
                page_path=source.page_path,
                source_file=source.source_file,
                base_url=source.base_url,
                is_homepage_content=source.is_homepage_content,
                public=is_public,
                published=is_published,
                state=state,
            )
        )

    return StatusReport(
        pages=pages,
        deploy_target=str(deploy_dir) if deploy_dir else None,
    )


def _published_marker(page: PageStatus) -> str:
    """Return the display marker for published pages."""
    return " [published]" if page.published else ""


def _format_page_label(page: PageStatus) -> str:
    """Format a page path with shared status-report markers."""
    return f"{page.page_path}{_published_marker(page)}"


def _append_page_lines(
    lines: list[str],
    pages: list[PageStatus],
    *,
    prefix: str,
    formatter: Callable[[PageStatus], str] = _format_page_label,
) -> None:
    """Append consistently formatted page lines to a report."""
    for page in pages:
        lines.append(f"{prefix}{formatter(page)}")


def _append_page_section(
    lines: list[str],
    header: str,
    pages: list[PageStatus],
    *,
    prefix: str,
    formatter: Callable[[PageStatus], str] = _format_page_label,
    trailing_blank: bool = True,
) -> None:
    """Append a report section with consistent header, rows, and spacing."""
    lines.append(header)
    _append_page_lines(lines, pages, prefix=prefix, formatter=formatter)
    if trailing_blank:
        lines.append("")


def format_status_report(report: StatusReport, verbose: bool = False) -> str:
    """Format a status report for display.

    Args:
        report: The status report to format
        verbose: If True, list all pages including unchanged ones

    Returns:
        Formatted string for terminal output
    """
    lines: list[str] = []

    if report.deploy_target:
        lines.append(f"Comparing against deploy target: {report.deploy_target}")
        lines.append("")

    new = report.new_pages
    modified = report.modified_pages
    unchanged = report.unchanged_pages
    private = report.private_pages

    if new:
        _append_page_section(lines, f"New pages ({len(new)}):", new, prefix="  + ")

    if modified:
        _append_page_section(
            lines, f"Modified pages ({len(modified)}):", modified, prefix="  ~ "
        )

    if not new and not modified:
        lines.append("No new or modified pages.")
        lines.append("")

    if verbose and unchanged:
        _append_page_section(
            lines, f"Unchanged pages ({len(unchanged)}):", unchanged, prefix="    "
        )

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

    def _format_build_candidate(page: PageStatus) -> str:
        state = "forced" if force_rebuild else page.state
        return f"{page.page_path} ({state}){_published_marker(page)}"

    _append_page_section(
        lines,
        f"Would build ({len(build_candidates)}):",
        build_candidates,
        prefix="  + ",
        formatter=_format_build_candidate,
        trailing_blank=False,
    )

    unchanged = report.unchanged_pages
    if verbose and not force_rebuild and unchanged:
        lines.append("")
        _append_page_section(
            lines,
            f"Cached/unchanged ({len(unchanged)}):",
            unchanged,
            prefix="    ",
            trailing_blank=False,
        )

    private = report.private_pages
    if private:
        lines.append("")
        private_pages = private if verbose else []
        _append_page_section(
            lines,
            f"Private pages ({len(private)}, skipped)",
            private_pages,
            prefix="  - ",
            trailing_blank=False,
        )

    lines.append("")
    lines.append(
        "Summary: "
        + ", ".join(
            [
                f"{len(report.public_pages)} public",
                f"{len(report.published_pages)} published",
                f"{len(build_candidates)} would build",
                f"{len(private)} private",
            ]
        )
    )

    return "\n".join(lines)
