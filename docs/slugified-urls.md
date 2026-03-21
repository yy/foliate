# Spec: Slugified URLs

## Problem

Pages with spaces in filenames produce URLs with `%20` encoding (e.g., `/wiki/Accessible%20PDF%20from%20LaTeX/`). While functional, these are ugly when copied/shared.

## Goal

Generate clean, hyphenated URLs while preserving backwards compatibility with existing `%20` URLs.

## Approach

- **Primary URL**: spaces replaced with hyphens (e.g., `/wiki/Accessible-PDF-from-LaTeX/`)
- **Legacy URL**: original `%20` path also generated (same `index.html` copied to both directories)
- **Canonical link**: legacy pages include `<link rel="canonical" href="...hyphenated...">` pointing to the primary URL
- **Internal links**: all `<a>` hrefs use the hyphenated version
- **Sitemap/search/feed**: only list hyphenated URLs

## Scope

Applies to the full URL path—both folder names and page names are slugified.

## Slugification rules

1. Replace spaces with hyphens
2. Preserve case (no lowercasing)—keeps consistency with Obsidian filenames
3. Collapse multiple consecutive hyphens into one
4. No other character transformations (apostrophes, special chars stay as-is for now)

Examples:
- `Accessible PDF from LaTeX` → `Accessible-PDF-from-LaTeX`
- `Charlottesville/Bike and pedestrian infrastructure` → `Charlottesville/Bike-and-pedestrian-infrastructure`
- `Earth mover's distance` → `Earth-mover's-distance`

## Implementation

### 1. Add `slugify_urls` config option

In `config.toml`:

```toml
[build]
slugify_urls = true   # default: true for new sites (foliate init)
```

### 2. Add slugify helper

New utility function:

```python
def slugify_path(path: str) -> str:
    """Replace spaces with hyphens in each segment of a path."""
    parts = path.split("/")
    return "/".join(re.sub(r"-{2,}", "-", part.replace(" ", "-")) for part in parts)
```

### 3. Modify `get_output_path()` in `build.py`

When `slugify_urls` is enabled, the primary output path uses `slugify_path(page_path)`:

```python
def get_output_path(build_dir, page_path, base_url, wiki_dir_name, slugify=False):
    slug = slugify_path(page_path) if slugify else page_path
    if base_url == "/":
        return build_dir / slug / "index.html"
    return build_dir / wiki_dir_name / slug / "index.html"
```

### 4. Generate legacy redirects

After writing the primary `index.html`, if the slugified path differs from the original, write a lightweight redirect stub at the original (space-based) path. This avoids duplicating full page content for every page with spaces.

```python
REDIRECT_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<link rel="canonical" href="{canonical_url}">
<meta http-equiv="refresh" content="0; url={canonical_url}">
<title>Redirecting…</title>
</head>
<body><a href="{canonical_url}">Redirecting…</a></body>
</html>
"""

def write_legacy_redirect(legacy_output_path, canonical_url):
    """Write a redirect stub at the legacy path."""
    legacy_output_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_output_path.write_text(REDIRECT_TEMPLATE.format(canonical_url=canonical_url))
```

### 5. Update link generation

In `markdown_utils.py`, the wikilink extension's `base_url` handling and `fix_homepage_to_wiki_links()` should produce slugified hrefs:

- Wikilinks: `[[Accessible PDF from LaTeX]]` → `href="/wiki/Accessible-PDF-from-LaTeX/"`
- Homepage-to-wiki links: same transformation

### 6. Update search index, sitemap, and feed

In `generate_search_index()`, `generate_sitemap()`, and `generate_feed()`: use slugified URLs for the `url` field.

### 7. Update postprocessing

`extract_wiki_path()` in `postprocess.py` must handle both hyphenated and space-encoded paths when checking against the public pages set. Normalize incoming paths by replacing hyphens back to spaces for lookup:

```python
def normalize_wiki_path(path: str) -> str:
    """Normalize path for lookup (hyphens → spaces)."""
    return path.replace("-", " ")
```

**Caveat**: this creates ambiguity if a page name legitimately contains hyphens. To handle this, maintain a lookup dict mapping both the original and slugified paths to the page object.

### 8. Cache invalidation

When `slugify_urls` is first enabled, force a full rebuild (similar to config change detection in `cache.py`). The config mtime check already handles this.

## Edge cases

- **Pages with hyphens in the original name**: `A-B test.md` → `A-B-test` (no ambiguity in output, but legacy path lookup needs the mapping dict)
- **Collisions**: `my-page.md` and `my page.md` would both slugify to `my-page`. Detect at build time and error with a clear message.
- **Anchors**: fragment identifiers (`#section`) are unaffected
- **Assets**: asset paths in `/assets/` are not slugified (images/PDFs keep original names)

## Testing

- Unit test `slugify_path()` with spaces, hyphens, apostrophes, nested paths
- Test collision detection
- Test that legacy redirects have canonical tags and meta refresh
- Test that internal links use slugified URLs
- Test that search.json and sitemap.txt use slugified URLs
- Integration test: build a vault with spaced filenames, verify both paths serve content

## Migration

- Default is `slugify_urls = true` for new sites (`foliate init`), `false` for existing configs without the key—no behavior change for existing users
- When enabled, old URLs continue to work (legacy redirects)
- Search engines migrate via canonical tags over time
