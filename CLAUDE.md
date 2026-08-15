# CLAUDE.md

`foliate`: static site generator — markdown vault (Obsidian-style) in, HTML
site out. Python/uv, click CLI, Jinja2 templates. Features, commands, config,
deployment: `README.md`. Full config reference:
`src/foliate/defaults/config.toml`. Customization/themes/examples: `docs/`.

## Workflow

- Handoff check: `uv run ruff format . && uv run ruff check . && make ci`
  (mypy + pytest + build).
- **CI runs on Windows too.** Green local run ≠ green CI. For filesystem,
  time, process, or signal changes, explicitly check Windows behavior.
- Test against a real vault from the vault dir:
  `uv run --project ~/git/foliate foliate status` — keeps cwd, avoids uvx
  cache staleness.
- Releases: follow `docs/releasing.md`. Version lives in BOTH
  `pyproject.toml` and `src/foliate/__init__.py`; add a `docs/releases/` entry.

## Non-obvious

- Visibility is two-tiered and default-private: `public: true` → built but
  unlisted; add `published: true` for listings/search/feed.
- `_private/` is never built; `_homepage/` deploys to site root; everything
  else lands under `/wiki/`.
- Bare-URL autolinking is in-house (`autolink.py`) — don't re-add
  `mdx-linkify`/`bleach` (removed as unmaintained).
- Incremental builds cache by mtime; config or template changes force a full
  rebuild.
- Windows has no `time.tzset`, `fork`, POSIX signals, or POSIX user/group
  APIs; inherently POSIX tests need a skip. `TZ` does not affect Windows time.
- Use `Path` objects for path assertions; Windows uses backslashes. Close file
  handles before rename/delete, pass UTF-8 explicitly, and don't rely on case.
- Past Windows CI fixes worth checking when nearby: `643fa18` (timezone test),
  `d947726`/`ebf6a5b` (path separators), `45b39d0` (bundled-template staleness).
- Keep dependencies minimal.
