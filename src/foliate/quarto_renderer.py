"""Internal Quarto-to-Markdown renderer for Foliate."""

from __future__ import annotations

import hashlib
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


_INLINE_EXPRESSION = re.compile(r"`\{[A-Za-z][\w.+-]*\}\s+[^`\n]+`")


def _has_inline_expressions(qmd_file: Path) -> bool:
    """Return whether a QMD uses executable inline code outside fences."""
    in_fence = False
    fence_character = ""
    fence_length = 0

    for line in qmd_file.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        fence = re.match(r"(`{3,}|~{3,})", stripped)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                in_fence = False
            continue
        if not in_fence and _INLINE_EXPRESSION.search(line):
            return True

    return False


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

    # Quarto sometimes emits GFM figures as an image followed by an ordinary
    # numbered paragraph instead of a <figure>/<figcaption> wrapper. Preserve
    # the caption distinction using Foliate's existing italic-caption markup.
    content = re.sub(
        r"(?m)(!\[[^\]\n]*\]\([^\n]+\)\n\n)"
        r"(Figure(?:\u00a0| )\d+:[^\n]+)$",
        r"\1*\2*",
        content,
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
    asset_url_prefix: str,
) -> None:
    """Point rendered Markdown at Foliate's generated-asset directory."""
    content = md_file.read_text(encoding="utf-8")
    stem = md_file.stem
    encoded_stem = quote(stem)
    url_prefix = asset_url_prefix.rstrip("/")
    parent = relative_source.parent
    if parent == Path("."):
        new_base = f"{url_prefix}/{encoded_stem}/"
    else:
        new_base = f"{url_prefix}/{quote(parent.as_posix())}/{encoded_stem}/"

    for candidate in (stem, encoded_stem):
        figure_dir = rf"{re.escape(candidate)}_files/figure-[^/]+/"
        content = re.sub(figure_dir, new_base, content)
        content = content.replace(f"{candidate}_files/", new_base)
    md_file.write_text(content, encoding="utf-8")


def _sync_figure_assets(source_dir: Path | None, target_dir: Path) -> None:
    """Promote generated figures without rewriting unchanged destination files."""
    sources = (
        {path.name: path for path in source_dir.rglob("*") if path.is_file()}
        if source_dir is not None and source_dir.is_dir()
        else {}
    )

    if sources:
        target_dir.mkdir(parents=True, exist_ok=True)

    for name, source in sources.items():
        destination = target_dir / name
        same_size = (
            destination.is_file()
            and source.stat().st_size == destination.stat().st_size
        )
        if same_size:
            with source.open("rb") as source_file, destination.open(
                "rb"
            ) as destination_file:
                source_hash = hashlib.file_digest(source_file, "sha256").digest()
                destination_hash = hashlib.file_digest(
                    destination_file, "sha256"
                ).digest()
            if source_hash == destination_hash:
                continue

        target_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{name}.", suffix=".foliate-tmp", dir=target_dir, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            shutil.copy2(source, temporary_path)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)

    if target_dir.is_dir():
        for existing in target_dir.iterdir():
            if existing.is_file() and existing.name in sources:
                continue
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
        if not any(target_dir.iterdir()):
            target_dir.rmdir()


def render_qmd(
    qmd_file: Path,
    pages_dir: Path,
    cache_dir: Path,
    assets_dir: Path,
    asset_url_prefix: str = "/assets/quarto",
    python: str | None = None,
    verbose: bool = False,
    refresh_cache: bool = False,
) -> Path | None:
    """Render one QMD source to GFM and promote its generated figures."""
    relative_source = qmd_file.relative_to(pages_dir)
    output_md = qmd_file.with_suffix(".md")
    original_frontmatter = _extract_frontmatter(qmd_file)
    cell_widths = _extract_cell_widths(qmd_file)
    use_execution_cache = not _has_inline_expressions(qmd_file)
    if verbose:
        print(f"  Rendering: {relative_source}")
        if cell_widths:
            print(f"  Found widths: {cell_widths}")
        if not use_execution_cache:
            print("  Inline expression found; rendering without Jupyter Cache")

    execution_cache = cache_dir / "execution" / relative_source.parent / qmd_file.stem
    if use_execution_cache:
        execution_cache.mkdir(parents=True, exist_ok=True)
    local_figures = qmd_file.with_name(f"{qmd_file.stem}_files")
    if local_figures.exists():
        shutil.rmtree(local_figures)

    command = [
        "quarto",
        "render",
        qmd_file.name,
        "--to",
        "gfm",
        "--metadata",
        "from:markdown-smart",
        "--wrap=none",
        "--cache" if use_execution_cache else "--no-cache",
        "--output",
        output_md.name,
        "--execute-dir",
        str(qmd_file.parent),
    ]
    if refresh_cache and use_execution_cache:
        command.append("--cache-refresh")

    render_environment = {
        **os.environ,
        **({"JUPYTERCACHE": str(execution_cache)} if use_execution_cache else {}),
        **({"QUARTO_PYTHON": python} if python else {}),
    }

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=qmd_file.parent,
            env=render_environment,
        )
    except subprocess.TimeoutExpired:
        print(f"  Timeout rendering {qmd_file.name}")
        if local_figures.exists():
            shutil.rmtree(local_figures)
        return None
    if result.returncode != 0:
        print(f"  Error rendering {qmd_file.name}: {result.stderr}")
        if local_figures.exists():
            shutil.rmtree(local_figures)
        return None

    _fix_figure_paths(output_md, relative_source, asset_url_prefix)
    _strip_html_wrappers(output_md, cell_widths=cell_widths, verbose=verbose)
    _merge_frontmatter(output_md, original_frontmatter)

    target = assets_dir / relative_source.parent / qmd_file.stem
    _sync_figure_assets(local_figures if local_figures.exists() else None, target)
    if local_figures.exists():
        shutil.rmtree(local_figures)
    return output_md
