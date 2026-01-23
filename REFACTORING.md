# Foliate Refactoring Tasks

## Completed

- [x] Consolidate `importlib.resources` patterns → `resources.py`
- [x] Create `expand_path()` utility
- [x] Simplify config loading with `_load_dataclass()` helper
- [x] Remove unused `label` parameter from `copy_directory_incremental()`
- [x] Remove unused `homepage_pages` parameter from `fix_homepage_to_wiki_links()`
- [x] Remove stale comment in build.py
- [x] Break down `process_markdown_files()` → `iter_public_md_files()` + `process_single_md_file()`
- [x] Consolidate HTTP server startup → `start_dev_server()` in `resources.py`
- [x] Standardize type annotations (`Optional[X]` → `X | None`)

## Medium Priority

- [ ] **Make "Home" page configurable** (`build.py:139,272`)
  - Add `home_page` setting to `BuildConfig`

## Low Priority

- [ ] Replace global `_markdown_cache` dict with `functools.lru_cache`
- [ ] Simplify `extract_description()` regex chain (73 lines)
- [ ] Add tests for `resources.py` utilities
