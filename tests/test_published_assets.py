"""Tests for optional remote publication of generated assets."""

from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import Mock

import pytest

from foliate.config import Config
from foliate.published_assets import (
    AssetPublicationError,
    PublisherConfig,
    generated_asset_key,
    get_generated_asset_root,
    load_publisher_config,
    prepare_published_build,
    public_asset_url,
)


def _config(tmp_path: Path, *, publisher: bool = True) -> Config:
    foliate_dir = tmp_path / ".foliate"
    foliate_dir.mkdir()
    config_path = foliate_dir / "config.toml"
    config_path.write_text("[advanced]\nquarto_enabled = true\n", encoding="utf-8")
    if publisher:
        (foliate_dir / "assets.toml").write_text(
            """\
[publisher]
command = ["uploader", "{staging_prefix_dir}"]
public_base_url = "https://cdn.example/public/imgs"
key_prefix = "quarto"
""",
            encoding="utf-8",
        )
    return Config.load(config_path)


def _build_with_assets(config: Config) -> tuple[Path, Path, Path]:
    build_dir = config.get_build_dir()
    asset = build_dir / "assets" / "quarto" / "My Page" / "plot one.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"plot")
    unused = build_dir / "assets" / "quarto" / "Private" / "unused.png"
    unused.parent.mkdir(parents=True)
    unused.write_bytes(b"private")
    html = build_dir / "wiki" / "My-Page" / "index.html"
    html.parent.mkdir(parents=True)
    html.write_text(
        '<meta content="https://example.com/assets/quarto/My Page/plot one.png">\n'
        '<img src="/assets/quarto/My%20Page/plot%20one.png">',
        encoding="utf-8",
    )
    return build_dir, asset, html


def test_local_sites_keep_generated_assets_in_vault(tmp_path):
    config = _config(tmp_path, publisher=False)

    assert get_generated_asset_root(config) == tmp_path / "assets" / "quarto"

    build_dir = tmp_path / ".foliate" / "build"
    result = prepare_published_build(config, build_dir)
    assert result.path == build_dir
    assert result.asset_count == 0


def test_configured_sites_keep_generated_assets_in_cache(tmp_path):
    config = _config(tmp_path)

    assert get_generated_asset_root(config) == (
        tmp_path / ".foliate" / "cache" / "quarto" / "assets"
    )


def test_load_publisher_config_requires_staging_command(tmp_path):
    config = _config(tmp_path)
    (tmp_path / ".foliate" / "assets.toml").write_text(
        "[publisher]\n"
        'command = ["upload"]\n'
        'public_base_url = "https://cdn.example"\n',
        encoding="utf-8",
    )

    with pytest.raises(AssetPublicationError, match="staging_dir"):
        load_publisher_config(config)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("public_base_url", '"s3://bucket/path"', "HTTP"),
        ("key_prefix", '"quarto/../private"', "safe URL path"),
        ("key_prefix", '"quarto\\\\figures"', "safe URL path"),
    ],
)
def test_load_publisher_config_rejects_unsafe_urls_and_keys(
    tmp_path, field, value, message
):
    config = _config(tmp_path)
    values = {
        "public_base_url": '"https://cdn.example/assets"',
        "key_prefix": '"quarto"',
    }
    values[field] = value
    (tmp_path / ".foliate" / "assets.toml").write_text(
        "[publisher]\n"
        'command = ["upload", "{staging_dir}"]\n'
        f"public_base_url = {values['public_base_url']}\n"
        f"key_prefix = {values['key_prefix']}\n",
        encoding="utf-8",
    )

    with pytest.raises(AssetPublicationError, match=message):
        load_publisher_config(config)


def test_generated_asset_url_is_stable_and_encoded():
    publisher = PublisherConfig(
        command=("upload", "{staging_dir}"),
        public_base_url="https://cdn.example/public/imgs",
    )

    key = generated_asset_key(Path("My Page/plot one.png"), publisher)

    assert key == "quarto/My Page/plot one.png"
    assert public_asset_url(key, publisher) == (
        "https://cdn.example/public/imgs/"
        "quarto/My%20Page/plot%20one.png"
    )


def test_prepare_dry_run_rewrites_copy_and_stages_only_referenced_assets(
    tmp_path, monkeypatch
):
    config = _config(tmp_path)
    build_dir, asset, html = _build_with_assets(config)
    upload = Mock()
    monkeypatch.setattr("foliate.published_assets.subprocess.run", upload)

    result = prepare_published_build(config, build_dir, dry_run=True)

    assert result.path != build_dir
    assert result.asset_count == 1
    assert upload.call_count == 0
    assert asset.exists()
    assert "/assets/quarto/" in html.read_text(encoding="utf-8")

    deploy_html = result.path / html.relative_to(build_dir)
    deploy_content = deploy_html.read_text(encoding="utf-8")
    assert deploy_content.count(
        "https://cdn.example/public/imgs/quarto/My%20Page/"
    ) == 2
    assert "https://example.comhttps://" not in deploy_content
    assert not (result.path / "assets" / "quarto").exists()

    staged = list((config.get_cache_dir() / "publisher" / "staging").rglob("*.png"))
    assert len(staged) == 1
    assert staged[0].read_bytes() == b"plot"


def test_prepare_published_build_runs_one_tree_upload(tmp_path, monkeypatch):
    config = _config(tmp_path)
    build_dir, _asset, _html = _build_with_assets(config)
    upload = Mock()
    monkeypatch.setattr("foliate.published_assets.subprocess.run", upload)

    result = prepare_published_build(config, build_dir)

    assert result.asset_count == 1
    upload.assert_called_once()
    assert upload.call_args.kwargs == {"check": True}
    command = upload.call_args.args[0]
    assert command[0] == "uploader"
    assert Path(command[1]).is_dir()


def test_publish_command_can_target_only_the_managed_prefix(tmp_path, monkeypatch):
    config = _config(tmp_path)
    (tmp_path / ".foliate" / "assets.toml").write_text(
        "[publisher]\n"
        'command = ["sync", "{staging_prefix_dir}", "remote/{key_prefix}"]\n'
        'public_base_url = "https://cdn.example/public/imgs"\n'
        'key_prefix = "quarto"\n',
        encoding="utf-8",
    )
    build_dir, _asset, _html = _build_with_assets(config)
    upload = Mock()
    monkeypatch.setattr("foliate.published_assets.subprocess.run", upload)

    prepare_published_build(config, build_dir)

    command = upload.call_args.args[0]
    assert command[0] == "sync"
    assert Path(command[1]).name == "quarto"
    assert command[2] == "remote/quarto"


def test_empty_public_asset_set_still_syncs_for_remote_deletion(
    tmp_path, monkeypatch
):
    config = _config(tmp_path)
    build_dir = config.get_build_dir()
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("No figures", encoding="utf-8")
    upload = Mock()
    monkeypatch.setattr("foliate.published_assets.subprocess.run", upload)

    result = prepare_published_build(config, build_dir)

    assert result.asset_count == 0
    upload.assert_called_once()
    prefix_dir = Path(upload.call_args.args[0][1])
    assert prefix_dir.name == "quarto"
    assert prefix_dir.is_dir()


def test_prepare_published_build_propagates_upload_failure(tmp_path, monkeypatch):
    config = _config(tmp_path)
    build_dir, _asset, _html = _build_with_assets(config)

    def fail(*_args, **_kwargs):
        raise CalledProcessError(1, "uploader")

    monkeypatch.setattr("foliate.published_assets.subprocess.run", fail)

    with pytest.raises(AssetPublicationError, match="upload failed"):
        prepare_published_build(config, build_dir)
