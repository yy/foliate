"""Regression tests for clean command path edge cases."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from foliate.cli import main


@pytest.mark.parametrize("artifact_name", ["build", "cache"])
def test_clean_removes_conflicting_artifact_file(artifact_name: str):
    """clean should remove stray files at build/cache artifact paths."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        artifact_path = Path(".foliate") / artifact_name
        artifact_path.parent.mkdir(parents=True)
        artifact_path.write_text("not a directory", encoding="utf-8")

        result = runner.invoke(main, ["clean"])

        assert result.exit_code == 0
        assert not artifact_path.exists()
        assert "Removed " in result.output
        assert artifact_name in result.output
