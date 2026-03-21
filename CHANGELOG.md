# Changelog

## Unreleased

### Added
- **Slugified URLs**: Replace spaces with hyphens in URLs for cleaner links (e.g., `/wiki/My-Page/` instead of `/wiki/My%20Page/`). Legacy space-based URLs get lightweight redirect stubs with canonical tags. Enable with `slugify_urls = true` in `[build]` config (default for new sites via `foliate init`).
- Collision detection: build errors clearly when two pages would produce the same slugified URL (e.g., `my-page.md` and `my page.md`).

## 0.6.0 - 2026-03-06

### Changed
- Introduce typed `Page` dataclass to replace untyped dicts throughout the build pipeline.

### Added
- `nl2br` config option to convert single newlines to `<br>` tags (Obsidian-style).

## 0.5.3 - 2026-03-06

### Fixed
- Deploy dry-run now correctly detects changes from rsync output.
- Build ignores `.foliate/` markdown files.
- Homepage link rewrite handles apostrophes in href paths.
- Feed typing imports.
- Status comparison for non-git deploy targets.

## 0.5.2 - 2026-03-01

### Fixed
- Thread-safety crash in watch mode markdown rendering.
- Windows CI: escape backslashes in deploy path for TOML.

## 0.5.1 - 2026-03-01

### Fixed
- Status showing all pages as "modified" after reinstall.
- Wikilinks with backticks being sanitized as private pages.
- Recent pages link click area extending to full row width.
- Status module: cache clearing, shared paths, `.qmd` support, dry-run output.

### Added
- Remove stale HTML when pages become private or are deleted.

## 0.5.0 - 2026-02-28

### Added
- `foliate status` command to preview build changes without building.

## 0.4.5 - 2026-02-18

### Fixed
- Watch-mode wikilink sanitization regression.
- Watch falsely reporting server started when port is occupied.

### Added
- Document `home_page` config option in default template.

## 0.4.4 - 2026-02-14

### Fixed
- Windows compatibility.

### Added
- GitHub Actions CI workflow (Linux, macOS, Windows; Python 3.12/3.13).
- Release documentation.

## 0.4.3 - 2026-02-08

### Fixed
- Incremental feed/site artifact generation.

## 0.4.2 - 2026-02-08

### Fixed
- Build/watch/deploy edge cases.

## 0.4.1 - 2026-02-08

### Fixed
- `shutil.rmtree` failures during watch mode on macOS.
