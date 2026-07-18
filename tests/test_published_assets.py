"""Tests for publication-gated generated assets."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from foliate.cli import main
from foliate.config import AdvancedConfig, Config
from foliate.published_assets import (
    AssetPublicationError,
    PublishResult,
    apply_published_asset_urls,
    get_managed_asset_dir,
    is_published_page,
    load_publisher_config,
    publish_page_assets,
)
from foliate.quarto import get_cached_markdown_path, get_quarto_asset_dir


def _config(tmp_path: Path) -> Config:
    foliate_dir = tmp_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text("[advanced]\nquarto_enabled = true\n", encoding="utf-8")
    (foliate_dir / "assets.toml").write_text(
        """\
[publisher]
command = ["uploader", "{source}", "{key}"]
url_template = "https://cdn.example/{key}"
key_template = "{page_slug}/{filename}"
""",
        encoding="utf-8",
    )
    config = Config.load(config_path)
    config.advanced = AdvancedConfig(quarto_enabled=True)
    return config


def _page(tmp_path: Path, *, published: bool) -> Path:
    page = tmp_path / "My Page.qmd"
    page.write_text(
        "---\n"
        "title: My Page\n"
        f"published: {'true' if published else 'false'}\n"
        "publish_assets: true\n"
        "---\n",
        encoding="utf-8",
    )
    return page


def test_managed_quarto_assets_use_draft_root(tmp_path):
    config = _config(tmp_path)
    page = _page(tmp_path, published=False)

    expected = tmp_path / "assets" / "drafts" / "quarto" / "My Page"

    assert get_managed_asset_dir(config, page) == expected
    assert get_quarto_asset_dir(config, page) == expected


def test_publish_refuses_unpublished_page(tmp_path):
    config = _config(tmp_path)
    page = _page(tmp_path, published=False)

    with pytest.raises(AssetPublicationError, match="published: true"):
        publish_page_assets(config, page)


def test_publish_uploads_rewrites_manifest_and_removes_drafts(
    tmp_path, monkeypatch
):
    config = _config(tmp_path)
    page = _page(tmp_path, published=True)
    asset_dir = get_managed_asset_dir(config, page)
    assert asset_dir is not None
    cached = get_cached_markdown_path(config, page)
    assert cached is not None

    def fake_preprocess(*_args, **_kwargs):
        asset_dir.mkdir(parents=True)
        (asset_dir / "plot.png").write_bytes(b"plot")
        cached.parent.mkdir(parents=True)
        cached.write_text(
            "![](/assets/drafts/quarto/My%20Page/plot.png)\n", encoding="utf-8"
        )
        return {str(page.resolve()): str(cached)}

    monkeypatch.setattr("foliate.quarto.preprocess_quarto", fake_preprocess)
    upload = Mock()
    monkeypatch.setattr("foliate.published_assets.subprocess.run", upload)

    result = publish_page_assets(config, page)

    assert result.discovered == 1
    assert result.uploaded == 1
    assert result.unchanged == 0
    upload.assert_called_once()
    command = upload.call_args.args[0]
    assert command[0] == "uploader"
    assert command[2] == "My-Page/plot.png"
    assert cached.read_text(encoding="utf-8") == (
        "![](https://cdn.example/My-Page/plot.png)\n"
    )
    assert not asset_dir.exists()

    manifest = json.loads(
        (tmp_path / ".foliate" / "published-assets.json").read_text(
            encoding="utf-8"
        )
    )
    entry = manifest["assets"][
        "assets/drafts/quarto/My Page/plot.png"
    ]
    assert entry["key"] == "My-Page/plot.png"
    assert entry["url"] == "https://cdn.example/My-Page/plot.png"


def test_build_rewrite_rejects_changed_generated_asset(tmp_path):
    config = _config(tmp_path)
    page = _page(tmp_path, published=True)
    asset_dir = get_managed_asset_dir(config, page)
    assert asset_dir is not None
    asset_dir.mkdir(parents=True)
    asset = asset_dir / "plot.png"
    asset.write_bytes(b"new plot")
    relative = "assets/drafts/quarto/My Page/plot.png"
    manifest = {
        "version": 1,
        "assets": {
            relative: {
                "page": "My Page",
                "sha256": "old-hash",
                "key": "My-Page/plot.png",
                "url": "https://cdn.example/My-Page/plot.png",
            }
        },
    }
    (tmp_path / ".foliate" / "published-assets.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    with pytest.raises(AssetPublicationError, match="generated asset changed"):
        apply_published_asset_urls(
            config,
            page,
            "![](/assets/drafts/quarto/My%20Page/plot.png)\n",
        )


def test_load_publisher_config_requires_command_array(tmp_path):
    config = _config(tmp_path)
    (tmp_path / ".foliate" / "assets.toml").write_text(
        '[publisher]\ncommand = "upload"\nurl_template = "https://x/{key}"\n',
        encoding="utf-8",
    )

    with pytest.raises(AssetPublicationError, match="array of strings"):
        load_publisher_config(config)


def test_cli_publish_assets_reports_unpublished_gate(tmp_path, monkeypatch):
    config = _config(tmp_path)
    page = _page(tmp_path, published=False)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["publish-assets", page.name])

    assert result.exit_code == 1
    assert "set 'published: true' first" in result.output
    assert not (config.get_foliate_dir() / "published-assets.json").exists()


def test_cli_build_reports_manifest_error_without_traceback(tmp_path, monkeypatch):
    _config(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch(
        "foliate.build.build",
        side_effect=AssetPublicationError("generated asset changed"),
    ):
        result = CliRunner().invoke(main, ["build"])

    assert result.exit_code == 1
    assert result.output == "Error: generated asset changed\n"


def test_cli_set_published_rolls_back_when_upload_fails(tmp_path, monkeypatch):
    _config(tmp_path)
    page = _page(tmp_path, published=False)
    monkeypatch.chdir(tmp_path)

    def fail_after_gate(_config, qmd_file, **_kwargs):
        assert is_published_page(qmd_file)
        raise AssetPublicationError("upload failed")

    with patch("foliate.published_assets.publish_page_assets", fail_after_gate):
        result = CliRunner().invoke(
            main, ["publish-assets", page.name, "--set-published"]
        )

    assert result.exit_code == 1
    assert "upload failed" in result.output
    assert "published: false" in page.read_text(encoding="utf-8")


def test_cli_set_published_keeps_true_after_success(tmp_path, monkeypatch):
    _config(tmp_path)
    page = _page(tmp_path, published=False)
    monkeypatch.chdir(tmp_path)

    def succeed_after_gate(_config, qmd_file, **_kwargs):
        assert is_published_page(qmd_file)
        return PublishResult(discovered=1, uploaded=1, unchanged=0, dry_run=False)

    with patch("foliate.published_assets.publish_page_assets", succeed_after_gate):
        result = CliRunner().invoke(
            main, ["publish-assets", page.name, "--set-published"]
        )

    assert result.exit_code == 0
    assert "Uploaded 1 of 1 assets" in result.output
    assert "published: true" in page.read_text(encoding="utf-8")


def test_cli_set_published_dry_run_restores_false(tmp_path, monkeypatch):
    _config(tmp_path)
    page = _page(tmp_path, published=False)
    monkeypatch.chdir(tmp_path)

    def dry_run_after_gate(_config, qmd_file, **kwargs):
        assert is_published_page(qmd_file)
        assert kwargs["dry_run"] is True
        return PublishResult(discovered=2, uploaded=2, unchanged=0, dry_run=True)

    with patch("foliate.published_assets.publish_page_assets", dry_run_after_gate):
        result = CliRunner().invoke(
            main,
            ["publish-assets", page.name, "--set-published", "--dry-run"],
        )

    assert result.exit_code == 0
    assert "Would upload 2 of 2 assets" in result.output
    assert "published: false" in page.read_text(encoding="utf-8")
