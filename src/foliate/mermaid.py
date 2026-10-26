"""Render Mermaid code fences to inline SVG at build time with Pele.

Pele (https://github.com/obsidianmd/pele) is the renderer Obsidian uses for
Mermaid diagrams. Its bundle is vendored in ``foliate/pele/`` and runs under
``node``: one process per page that contains diagrams. Colors are CSS
variables (``--pele-*``), so the stylesheet themes the static SVG. Without
``node``, or when a diagram fails to parse, the fence stays a code block.
"""

import json
import shutil
import subprocess
from pathlib import Path

from markdown.extensions import Extension
from markdown.extensions.fenced_code import FencedBlockPreprocessor
from markdown.preprocessors import Preprocessor

from .logging import warning

RENDER_SCRIPT = Path(__file__).parent / "pele" / "render.mjs"
# Lay out for foliate's content column (at most 800px) and keep the source
# direction, as Obsidian does; the SVG scales down on narrower screens.
RENDER_OPTIONS = {"maxWidth": 720, "autoDirection": False}
RENDER_TIMEOUT_SECONDS = 60

_warned_unavailable = False


class DiagramRenderError(RuntimeError):
    """Raised when the renderer cannot run at all."""


def render_diagrams(sources: list[str]) -> list[dict[str, str]]:
    """Render Mermaid sources in one Node call.

    Returns one dict per source: ``{"svg": ...}`` or ``{"error": ...}``.
    """
    node = shutil.which("node")
    if node is None:
        raise DiagramRenderError("`node` not found on PATH")

    payload = json.dumps({"sources": sources, "options": RENDER_OPTIONS})
    try:
        proc = subprocess.run(
            [node, str(RENDER_SCRIPT)],
            input=payload.encode("utf-8"),
            capture_output=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DiagramRenderError(str(e)) from e

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").splitlines()
        detail = next((line for line in stderr if "Error" in line), "")
        raise DiagramRenderError(detail or f"node exited with {proc.returncode}")

    try:
        results = json.loads(proc.stdout.decode("utf-8"))
    except ValueError as e:
        raise DiagramRenderError(f"unreadable renderer output: {e}") from e
    if not isinstance(results, list) or len(results) != len(sources):
        raise DiagramRenderError("renderer returned the wrong number of diagrams")
    return results


def _warn_unavailable(reason: str) -> None:
    global _warned_unavailable  # noqa: PLW0603
    if not _warned_unavailable:
        warning(f"Mermaid diagrams left as code blocks: {reason}")
        _warned_unavailable = True


class MermaidPreprocessor(Preprocessor):
    """Replace ```mermaid fences with stashed SVG before fenced_code runs."""

    def run(self, lines: list[str]) -> list[str]:
        text = "\n".join(lines)
        blocks = [
            match
            for match in FencedBlockPreprocessor.FENCED_BLOCK_RE.finditer(text)
            if match.group("lang") == "mermaid"
        ]
        if not blocks:
            return lines

        try:
            results = render_diagrams([match.group("code") for match in blocks])
        except DiagramRenderError as e:
            _warn_unavailable(str(e))
            return lines

        source = getattr(self.md, "foliate_source", None) or "page"
        parts: list[str] = []
        position = 0
        for number, (match, result) in enumerate(zip(blocks, results), start=1):
            svg = result.get("svg")
            if not svg:
                error = result.get("error") or "render failed"
                warning(f"{source}: Mermaid diagram {number} left as code: {error}")
                continue
            # no-katex: KaTeX auto-render would rewrite $...$ inside SVG text.
            html = f'<div class="diagram no-katex">{svg}</div>'
            placeholder = self.md.htmlStash.store(html)
            parts.append(f"{text[position : match.start()]}\n{placeholder}\n")
            position = match.end()
        parts.append(text[position:])
        return "".join(parts).split("\n")


class MermaidExtension(Extension):
    def extendMarkdown(self, md) -> None:
        # After normalize_whitespace (30), before fenced_code_block (25) and
        # foliate_dollar_math (20), so diagram text reaches Pele untouched.
        md.preprocessors.register(MermaidPreprocessor(md), "foliate_mermaid", 26)


def makeExtension(**kwargs) -> MermaidExtension:  # noqa: N802
    return MermaidExtension(**kwargs)
