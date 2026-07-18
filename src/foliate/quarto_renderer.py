"""Internal Quarto-to-Markdown renderer for Foliate."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from datetime import date as date_type
from pathlib import Path
from urllib.parse import quote

import frontmatter

_QUARTO_FRONTMATTER_KEYS = {
    "bibliography",
    "cache",
    "citation",
    "code-annotations",
    "code-copy",
    "code-fold",
    "code-line-numbers",
    "code-link",
    "code-overflow",
    "code-summary",
    "code-tools",
    "crossref",
    "csl",
    "echo",
    "embed-resources",
    "engine",
    "error",
    "eval",
    "execute",
    "fig-align",
    "fig-alt",
    "fig-cap",
    "fig-dpi",
    "fig-env",
    "fig-format",
    "fig-height",
    "fig-pos",
    "fig-responsive",
    "fig-subcap",
    "fig-width",
    "filters",
    "format",
    "freeze",
    "include",
    "jupyter",
    "keep-hidden",
    "keep-ipynb",
    "keep-md",
    "knitr",
    "lightbox",
    "number-sections",
    "output",
    "prefer-html",
    "self-contained",
    "shift-heading-level-by",
    "shortcodes",
    "standalone",
    "tbl-cap",
    "tbl-colwidths",
    "tbl-subcap",
    "warning",
}


def is_quarto_available() -> bool:
    """Return whether the Quarto CLI can run."""
    try:
        result = subprocess.run(
            ["quarto", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _extract_cell_widths(qmd_file: Path) -> dict[str, str]:
    """Map Quarto cell labels or generated identifiers to pixel widths."""
    content = qmd_file.read_text(encoding="utf-8")
    cell_pattern = re.compile(r"```\{[^}]+\}\n(.*?)```", re.DOTALL)
    widths: dict[str, str] = {}
    cell_number = 1

    for match in cell_pattern.finditer(content):
        cell_number += 1
        cell = match.group(1)
        label_match = re.search(r"^#\|\s*label:\s*(\S+)", cell, re.MULTILINE)
        width_match = re.search(
            r'^#\|\s*out-width:\s*["\']?(\d+)(?:px)?["\']?',
            cell,
            re.MULTILINE,
        )
        if width_match:
            key = label_match.group(1) if label_match else f"cell-{cell_number}"
            widths[key] = width_match.group(1)
    return widths


def _extract_frontmatter(qmd_file: Path) -> dict[str, object]:
    """Read the source frontmatter, returning an empty mapping on failure."""
    try:
        post = frontmatter.load(qmd_file)
    except Exception:
        return {}
    return dict(post.metadata)


def _merge_frontmatter(md_file: Path, original: dict[str, object]) -> None:
    """Restore Foliate metadata and remove Quarto-only frontmatter."""
    try:
        post = frontmatter.load(md_file)
        metadata: dict[str, object] = {}
        for key, value in original.items():
            if key in _QUARTO_FRONTMATTER_KEYS or key.startswith(
                ("fig-", "tbl-", "code-", "html-", "pdf-")
            ):
                continue
            if key == "date" and value == "today":
                value = date_type.today().isoformat()
            metadata[key] = value
        post.metadata = metadata
        md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
    except Exception as error:
        print(f"  Warning: Could not merge frontmatter: {error}")


def _extract_width(html: str) -> str | None:
    width_match = re.search(r'width="(\d+)(?:px)?"', html)
    if width_match:
        return width_match.group(1)
    style_match = re.search(r'style="[^"]*width:\s*(\d+)(?:px)?[^"]*"', html)
    return style_match.group(1) if style_match else None


def _strip_html_wrappers(
    md_file: Path,
    cell_widths: dict[str, str] | None = None,
    verbose: bool = False,
) -> None:
    """Convert Quarto figure wrappers to Obsidian-compatible Markdown."""
    content = md_file.read_text(encoding="utf-8")
    cell_widths = cell_widths or {}
    if verbose and cell_widths:
        print(f"  Cell widths: {cell_widths}")

    content = re.sub(r"^# [^\n]+\n+\d{4}-\d{2}-\d{2}\n*", "", content)
    content = re.sub(r"<div[^>]*>\n?", "", content)
    content = re.sub(r"\n?</div>", "", content)

    def figure_to_markdown(match: re.Match[str]) -> str:
        figure = match.group(0)
        image = re.search(r'<img[^>]*src="([^"]*)"[^>]*/?>', figure)
        caption_match = re.search(
            r"<figcaption[^>]*>(.*?)</figcaption>", figure, re.DOTALL
        )
        if image is None:
            return figure
        path = image.group(1)
        caption = caption_match.group(1).strip() if caption_match else ""
        caption = re.sub(r"<[^>]+>", "", caption)
        width = _extract_width(figure)
        width_suffix = f"|{width}" if width else ""
        if caption:
            return f"![{caption}{width_suffix}]({path})\n\n*{caption}*"
        return f"![{width_suffix}]({path})"

    content = re.sub(
        r"<figure[^>]*>.*?</figure>",
        figure_to_markdown,
        content,
        flags=re.DOTALL,
    )

    def fix_broken_link(match: re.Match[str]) -> str:
        text = match.group(1).replace("\n", " ")
        url = match.group(2).replace("\n", "")
        return f"[{text}]({url})"

    content = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", fix_broken_link, content)
    content = re.sub(r"</?p>", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)

    if cell_widths:

        def apply_width(match: re.Match[str]) -> str:
            alt = match.group(1)
            path = match.group(2)
            filename = path.rsplit("/", maxsplit=1)[-1]
            for cell_id, width in cell_widths.items():
                if filename.startswith(f"{cell_id}-"):
                    if "|" not in alt:
                        return f"![{alt}|{width}]({path})"
                    break
            return match.group(0)

        content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", apply_width, content)

    md_file.write_text(content, encoding="utf-8")


def _fix_figure_paths(
    md_file: Path,
    relative_source: Path,
    assets_dir: Path,
    pages_dir: Path,
) -> None:
    """Point rendered Markdown at Foliate's generated-asset directory."""
    content = md_file.read_text(encoding="utf-8")
    stem = md_file.stem
    encoded_stem = quote(stem)
    assets_relative = assets_dir.relative_to(pages_dir)
    parent = relative_source.parent
    if parent == Path("."):
        new_base = f"/{assets_relative}/{encoded_stem}/"
    else:
        new_base = f"/{assets_relative}/{quote(parent.as_posix())}/{encoded_stem}/"

    for candidate in (stem, encoded_stem):
        figure_dir = rf"{re.escape(candidate)}_files/figure-[^/]+/"
        content = re.sub(figure_dir, new_base, content)
        content = content.replace(f"{candidate}_files/", new_base)
    md_file.write_text(content, encoding="utf-8")


def render_qmd(
    qmd_file: Path,
    pages_dir: Path,
    cache_dir: Path,
    assets_dir: Path,
    python: str | None = None,
    verbose: bool = False,
) -> Path | None:
    """Render one QMD source to GFM and relocate its generated figures."""
    relative_source = qmd_file.relative_to(pages_dir)
    output_md = qmd_file.with_suffix(".md")
    original_frontmatter = _extract_frontmatter(qmd_file)
    cell_widths = _extract_cell_widths(qmd_file)
    if verbose:
        print(f"  Rendering: {relative_source}")
        if cell_widths:
            print(f"  Found widths: {cell_widths}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix="execution-", dir=cache_dir
        ) as execution_cache:
            result = subprocess.run(
                [
                    "quarto",
                    "render",
                    qmd_file.name,
                    "--to",
                    "gfm",
                    "--wrap=none",
                    "--output",
                    output_md.name,
                    "--execute-dir",
                    str(qmd_file.parent),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=qmd_file.parent,
                env={
                    **os.environ,
                    "QUARTO_CACHE_PATH": execution_cache,
                    **({"QUARTO_PYTHON": python} if python else {}),
                },
            )
    except subprocess.TimeoutExpired:
        print(f"  Timeout rendering {qmd_file.name}")
        return None
    if result.returncode != 0:
        print(f"  Error rendering {qmd_file.name}: {result.stderr}")
        return None

    local_figures = qmd_file.with_name(f"{qmd_file.stem}_files")
    if local_figures.exists():
        target = assets_dir / relative_source.parent / qmd_file.stem
        target.mkdir(parents=True, exist_ok=True)
        for source in local_figures.rglob("*"):
            if source.is_file():
                destination = target / source.name
                if destination.exists():
                    destination.unlink()
                shutil.move(str(source), str(destination))
        shutil.rmtree(local_figures)
        _fix_figure_paths(output_md, relative_source, assets_dir, pages_dir)

    _strip_html_wrappers(output_md, cell_widths=cell_widths, verbose=verbose)
    _merge_frontmatter(output_md, original_frontmatter)
    return output_md
