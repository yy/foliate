"""Tests for Foliate's internal Quarto renderer."""

from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import frontmatter

from foliate.quarto_renderer import (
    _extract_cell_widths,
    _fix_figure_paths,
    _merge_frontmatter,
    _strip_html_wrappers,
    is_quarto_available,
    render_qmd,
)


def test_is_quarto_available(monkeypatch):
    monkeypatch.setattr(
        "foliate.quarto_renderer.subprocess.run",
        lambda *_args, **_kwargs: CompletedProcess([], 0),
    )

    assert is_quarto_available() is True


def test_is_quarto_available_handles_missing_executable(monkeypatch):
    def missing(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("foliate.quarto_renderer.subprocess.run", missing)

    assert is_quarto_available() is False


def test_extract_cell_widths_uses_labels_and_generated_ids(tmp_path):
    qmd_file = tmp_path / "page.qmd"
    qmd_file.write_text(
        """```{python}
#| label: speed-plot
#| out-width: 640px
1 + 1
```

```{python}
#| out-width: "420"
2 + 2
```
""",
        encoding="utf-8",
    )

    assert _extract_cell_widths(qmd_file) == {
        "speed-plot": "640",
        "cell-3": "420",
    }


def test_merge_frontmatter_keeps_foliate_fields(tmp_path):
    md_file = tmp_path / "page.md"
    md_file.write_text("---\nformat: gfm\n---\nBody\n", encoding="utf-8")

    _merge_frontmatter(
        md_file,
        {
            "title": "Page",
            "public": True,
            "published": False,
            "publish_assets": True,
            "format": "gfm",
            "fig-width": 8,
        },
    )

    metadata = frontmatter.load(md_file).metadata
    assert metadata == {
        "title": "Page",
        "public": True,
        "published": False,
        "publish_assets": True,
    }


def test_strip_html_wrappers_converts_caption_and_cell_width(tmp_path):
    md_file = tmp_path / "page.md"
    md_file.write_text(
        '<figure><img src="page_files/figure-commonmark/speed-plot-1.png" />'
        "<figcaption><strong>Speed</strong> change</figcaption></figure>\n",
        encoding="utf-8",
    )

    _strip_html_wrappers(md_file, {"speed-plot": "600"})

    assert md_file.read_text(encoding="utf-8") == (
        "![Speed change|600](page_files/figure-commonmark/speed-plot-1.png)\n\n"
        "*Speed change*\n"
    )


def test_fix_figure_paths_encodes_page_names(tmp_path):
    md_file = tmp_path / "nested" / "Page With Spaces.md"
    md_file.parent.mkdir()
    md_file.write_text(
        "![](Page%20With%20Spaces_files/figure-commonmark/plot.png)\n",
        encoding="utf-8",
    )

    _fix_figure_paths(
        md_file,
        Path("nested/Page With Spaces.qmd"),
        tmp_path / "assets" / "quarto",
        tmp_path,
    )

    assert md_file.read_text(encoding="utf-8") == (
        "![](/assets/quarto/nested/Page%20With%20Spaces/plot.png)\n"
    )


def test_render_qmd_uses_local_source_and_relocates_figures(monkeypatch, tmp_path):
    qmd_file = tmp_path / "nested" / "Page With Spaces.qmd"
    qmd_file.parent.mkdir()
    qmd_file.write_text(
        "---\ntitle: Page\npublic: true\n---\n\n```{python}\n1 + 1\n```\n",
        encoding="utf-8",
    )
    output_md = qmd_file.with_suffix(".md")
    observed: dict[str, object] = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["cwd"] = kwargs["cwd"]
        observed["python"] = kwargs["env"].get("QUARTO_PYTHON")
        observed["cache_exists"] = Path(kwargs["env"]["QUARTO_CACHE_PATH"]).is_dir()
        figure = (
            qmd_file.parent
            / "Page With Spaces_files"
            / "figure-commonmark"
            / "cell-2-output-1.png"
        )
        figure.parent.mkdir(parents=True)
        figure.write_bytes(b"png")
        output_md.write_text(
            "---\ntitle: Page\n---\n"
            "![](Page%20With%20Spaces_files/figure-commonmark/"
            "cell-2-output-1.png)\n",
            encoding="utf-8",
        )
        return CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("foliate.quarto_renderer.subprocess.run", fake_run)

    result = render_qmd(
        qmd_file=qmd_file,
        pages_dir=tmp_path,
        cache_dir=tmp_path / ".foliate" / "cache" / "quarto",
        assets_dir=tmp_path / "assets" / "quarto",
        python="/venv/bin/python",
    )

    assert result == output_md
    assert observed["args"][2] == qmd_file.name
    assert "--wrap=none" in observed["args"]
    assert observed["cwd"] == qmd_file.parent
    assert observed["python"] == "/venv/bin/python"
    assert observed["cache_exists"] is True
    assert (
        tmp_path
        / "assets"
        / "quarto"
        / "nested"
        / "Page With Spaces"
        / "cell-2-output-1.png"
    ).read_bytes() == b"png"
    assert "/assets/quarto/nested/Page%20With%20Spaces/cell-2-output-1.png" in (
        output_md.read_text(encoding="utf-8")
    )
    assert frontmatter.load(output_md).metadata == {"title": "Page", "public": True}


def test_render_qmd_returns_none_on_failure(monkeypatch, tmp_path):
    qmd_file = tmp_path / "page.qmd"
    qmd_file.write_text("# Page\n", encoding="utf-8")
    monkeypatch.setattr(
        "foliate.quarto_renderer.subprocess.run",
        lambda args, **_kwargs: CompletedProcess(args, 1, "", "failed"),
    )

    assert (
        render_qmd(qmd_file, tmp_path, tmp_path / "cache", tmp_path / "assets") is None
    )


def test_render_qmd_returns_none_on_timeout(monkeypatch, tmp_path):
    qmd_file = tmp_path / "page.qmd"
    qmd_file.write_text("# Page\n", encoding="utf-8")

    def timeout(*_args, **_kwargs):
        raise TimeoutExpired("quarto", 300)

    monkeypatch.setattr("foliate.quarto_renderer.subprocess.run", timeout)

    assert (
        render_qmd(qmd_file, tmp_path, tmp_path / "cache", tmp_path / "assets") is None
    )
