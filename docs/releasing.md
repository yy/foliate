# Releasing Foliate

## Purpose

This runbook defines a repeatable, manual release workflow with CI preflight checks.

## Prerequisites

1. PyPI credentials configured for `uv publish`.
2. Push access to `origin/main`.
3. A clean local clone of this repository.

## Preflight Checklist

1. Ensure your working tree is clean:

   ```bash
   git status --short
   ```

2. Ensure your local `main` is up to date:

   ```bash
   git checkout main
   git pull --ff-only
   ```

3. Confirm the latest `main` CI workflow is green in GitHub Actions.

## Version Bump

Update both version definitions:

1. `pyproject.toml` (`[project].version`)
2. `src/foliate/__init__.py` (`__version__`)

## Local Validation

Run tests and build locally before tagging:

```bash
uv run pytest -q
uv build
```

Or run the local CI parity target:

```bash
make ci
```

## Commit, Tag, and Push

```bash
git add pyproject.toml src/foliate/__init__.py
git add <other release changes>
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

## Publish to PyPI

```bash
make publish
```

`make publish` runs `uv build` and then `uv publish`.

## Post-Release Verification

1. Confirm the new version appears on PyPI.
2. Install and smoke test in a fresh environment:

   ```bash
   python -m pip install foliate==X.Y.Z
   foliate --version
   ```

## Recovery Notes

1. If publish fails before upload completes, fix the issue and rerun `make publish`.
2. If a bad release is published, cut an immediate patch release (`X.Y.(Z+1)`).
3. Do not rewrite or delete pushed release tags.
