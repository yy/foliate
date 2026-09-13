"""Configuration and build integration for optional heading folding."""

import logging

import pytest

from foliate import build
from foliate.config import Config


@pytest.fixture(autouse=True)
def isolate_build_logging(monkeypatch):
    # Avoid leaving handlers bound to pytest's temporary capture streams.
    monkeypatch.setattr("foliate.logging._logger", logging.getLogger(__name__))


@pytest.mark.parametrize("enabled", [None, False, True])
def test_heading_folding_build(tmp_path, enabled):
    """Only opted-in pages load the controls, with all source content visible."""
    foliate_dir = tmp_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    setting = "" if enabled is None else f"foldable_headings = {str(enabled).lower()}"
    config_path.write_text(f"[build]\n{setting}\n", encoding="utf-8")
    (tmp_path / "note.md").write_text(
        "---\npublic: true\n---\n## Alpha\n\nFirst paragraph.\n\n"
        "### Nested\n\nNested paragraph.\n\n## Beta\n\nLast paragraph.\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.build.foldable_headings is (enabled is True)
    assert config.to_template_context()["foldable_headings"] is (enabled is True)
    build.build(config=config)

    output = foliate_dir / "build"
    html = (output / "wiki" / "note" / "index.html").read_text(encoding="utf-8")
    assert ('src="/static/foldable-headings.js" defer' in html) is (enabled is True)
    assert ('href="/static/foldable-headings.css"' in html) is (enabled is True)
    assert '<h2 id="alpha">' in html
    assert "First paragraph." in html
    assert "Nested paragraph." in html
    assert "Last paragraph." in html
    assert '<div class="foldable-section"' not in html
    if enabled:
        assert (output / "static" / "foldable-headings.js").is_file()
        assert (output / "static" / "foldable-headings.css").is_file()


def test_heading_folding_toggle_invalidates_incremental_build(tmp_path):
    """Changing only the option must update an already-built page both ways."""
    foliate_dir = tmp_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    (tmp_path / "note.md").write_text(
        "---\npublic: true\n---\n## Alpha\n\nContent.\n", encoding="utf-8"
    )
    for enabled in (False, True, False):
        config_path.write_text(
            f"[build]\nfoldable_headings = {str(enabled).lower()}\n",
            encoding="utf-8",
        )
        build.build(config=Config.load(config_path))
        html = (foliate_dir / "build" / "wiki" / "note" / "index.html").read_text(
            encoding="utf-8"
        )
        assert ('src="/static/foldable-headings.js"' in html) is enabled
