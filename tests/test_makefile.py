from pathlib import Path


def test_makefile_bootstraps_dev_dependencies_for_test_targets():
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()

    assert "sync-dev:\n\tuv sync --frozen --extra dev\n" in makefile
    assert "\ntest: sync-dev\n\tuv run pytest\n" in makefile
    assert "\nci: sync-dev\n\tuv run mypy src/foliate\n\tuv run pytest -q\n\tuv build\n" in makefile
