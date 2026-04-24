from pathlib import Path

from foliate.doctor import _check_optional_directory


class TestCheckOptionalDirectory:
    def test_reports_directory_as_ok(self, tmp_path: Path):
        path = tmp_path / ".foliate" / "templates"
        path.mkdir(parents=True)

        warnings, ok = _check_optional_directory(
            path,
            base=tmp_path,
            label="User templates",
            missing_message=(
                "User templates directory not found (using bundled defaults)."
            ),
        )

        assert warnings == []
        assert ok == ["User templates directory: .foliate/templates"]

    def test_reports_file_as_warning(self, tmp_path: Path):
        path = tmp_path / ".foliate" / "static"
        path.parent.mkdir(parents=True)
        path.write_text("not a directory", encoding="utf-8")

        warnings, ok = _check_optional_directory(
            path,
            base=tmp_path,
            label="User static",
            missing_message="User static directory not found (using bundled defaults).",
        )

        assert warnings == ["User static path is not a directory: .foliate/static"]
        assert ok == []

    def test_reports_missing_path_with_fallback_message(self, tmp_path: Path):
        path = tmp_path / ".foliate" / "static"

        warnings, ok = _check_optional_directory(
            path,
            base=tmp_path,
            label="User static",
            missing_message="User static directory not found (using bundled defaults).",
        )

        assert warnings == []
        assert ok == ["User static directory not found (using bundled defaults)."]
