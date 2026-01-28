# Atom Feed Specification

This document specifies the Atom feed generation feature for foliate.

## Overview

Foliate generates an Atom feed for published wiki content. The feed distinguishes between **new pages** (individual entries) and **updated pages** (aggregated into a single digest entry), preventing feed spam from frequent wiki edits.

## Feed Format

### Atom 1.0
- **Path**: `/feed.xml`
- **Content-Type**: `application/atom+xml`
- **Specification**: [RFC 4287](https://tools.ietf.org/html/rfc4287)

Atom is chosen because it:
- Has a formal specification (RFC)
- Supports richer metadata
- Has better internationalization support
- Is supported by all modern feed readers

## Feed Entry Model

The feed contains two types of entries:

### 1. New Page Entries (Individual)

Each newly published page gets its own feed entry. A page is "new" when its publication date falls within the configured window.

```xml
<entry>
  <title>My New Article</title>
  <link href="https://example.com/wiki/MyNewArticle/" rel="alternate" type="text/html"/>
  <id>https://example.com/wiki/MyNewArticle/</id>
  <published>2024-03-15T00:00:00Z</published>
  <updated>2024-03-15T00:00:00Z</updated>
  <content type="html"><![CDATA[Full article content...]]></content>
</entry>
```

### 2. Recently Updated Entry (Digest)

All pages that have been modified (but not newly published) are aggregated into a single "Recently Updated Pages" entry. This entry:
- Has a stable `<id>` that doesn't change
- Has `<updated>` reflecting the most recent modification
- Contains a list of links to updated pages

```xml
<entry>
  <title>Recently Updated Pages</title>
  <link href="https://example.com/wiki/" rel="alternate" type="text/html"/>
  <id>https://example.com/feed/updates</id>
  <updated>2024-03-15T10:30:00Z</updated>
  <content type="html"><![CDATA[
    <p>The following pages were recently updated:</p>
    <ul>
      <li><a href="https://example.com/wiki/PageA/">PageA</a> - March 15, 2024</li>
      <li><a href="https://example.com/wiki/PageB/">PageB</a> - March 14, 2024</li>
      <li><a href="https://example.com/wiki/PageC/">PageC</a> - March 12, 2024</li>
    </ul>
  ]]></content>
</entry>
```

### New vs Updated Classification

| Condition | Classification |
|-----------|----------------|
| `published` date within window, never modified | New (individual entry) |
| `published` date within window, also modified | New (individual entry) |
| `published` date older than window, `modified` within window | Updated (digest entry) |
| Both dates older than window | Not in feed |

## Configuration

Add a `[feed]` section to `.foliate/config.toml`:

```toml
[feed]
enabled = true          # Master switch for feed generation
title = ""              # Feed title (defaults to site.name)
description = ""        # Feed description (defaults to "{site.name} - Recent updates")
language = "en"         # Language code (BCP 47)
items = 20              # Maximum number of new page entries
full_content = true     # Include full HTML content (false = summary only)
window = 30             # Days to include in feed (for both new and updated)
```

### Default Values

| Field | Default | Notes |
|-------|---------|-------|
| `enabled` | `true` | Set to `false` to disable feed generation |
| `title` | `site.name` | Inherited from `[site]` section |
| `description` | `"{site.name} - Recent updates"` | Auto-generated |
| `language` | `"en"` | Used in Atom `xml:lang` |
| `items` | `20` | Max new page entries; updated digest is always 1 entry |
| `full_content` | `true` | Full content for new pages; digest always shows links only |
| `window` | `30` | Days to look back for new/updated pages |

## Page Selection

### Inclusion Criteria

A page can appear in the feed if **all** of the following are true:

1. Has `published: true` or `published: <date>` in frontmatter
2. Has a **resolvable date** (see Date Handling below) - `published: true` alone is not sufficient
3. Is **not** in the `_homepage/` directory
4. Is **not** in an ignored folder (e.g., `_private/`)
5. Has `public: true` (required for the page to be built at all)
6. Has a `published` or `modified` date within the configured `window`

### Exclusion Rationale

- **`_homepage/` content**: These are site pages (About, Contact), not wiki posts
- **Unpublished pages**: `public: true` alone means "accessible but not listed"
- **Private folders**: Never built, so cannot be in feeds

## Date Handling

### Publication Date

Used to determine if a page is "new". Resolution order:

1. **`published` field** as date
   ```yaml
   published: 2024-03-15
   ```

2. **`date` field** (alternative)
   ```yaml
   date: 2024-03-15
   ```

3. **File modification time** (fallback via filesystem mtime)

### Modification Date

Used to determine if a page is "updated". Resolution order:

1. **`modified` field** in frontmatter (explicit)
   ```yaml
   modified: 2024-03-20
   ```

2. **File modification time** (filesystem mtime)

### Date Format Support

Accepted formats in frontmatter:

- ISO 8601 date: `2024-03-15`
- ISO 8601 datetime: `2024-03-15T10:30:00`
- With timezone: `2024-03-15T10:30:00+09:00`

All dates are normalized to RFC 3339 format for Atom output (`2024-03-15T00:00:00Z`).

### Deterministic Timestamps

Feed generation is deterministic. Timestamps reflect actual page dates, not build time:

| Element | Timestamp Source |
|---------|------------------|
| Feed `<updated>` | Most recent date across all entries (new or updated) |
| New entry `<published>` | Page's publication date |
| New entry `<updated>` | Page's modification date (or publication if unmodified) |
| Updates digest `<updated>` | Most recent modification date among updated pages |

This ensures rebuilding without content changes produces an identical feed, which matters for feed readers that check if the feed changed.

## Feed Structure

### Complete Atom Feed Example

```xml
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en">
  <title>My Wiki</title>
  <subtitle>My Wiki - Recent updates</subtitle>
  <link href="https://example.com/feed.xml" rel="self" type="application/atom+xml"/>
  <link href="https://example.com/" rel="alternate" type="text/html"/>
  <id>https://example.com/</id>
  <updated>2024-03-15T10:30:00Z</updated>
  <author>
    <name>Author Name</name>
  </author>
  <generator uri="https://github.com/yyahn/foliate" version="0.3.0">foliate</generator>

  <!-- New page entries (individual) -->
  <entry>
    <title>Brand New Article</title>
    <link href="https://example.com/wiki/BrandNewArticle/" rel="alternate" type="text/html"/>
    <id>https://example.com/wiki/BrandNewArticle/</id>
    <published>2024-03-15T00:00:00Z</published>
    <updated>2024-03-15T00:00:00Z</updated>
    <content type="html"><![CDATA[<p>Full article content here...</p>]]></content>
  </entry>

  <entry>
    <title>Another New Post</title>
    <link href="https://example.com/wiki/AnotherNewPost/" rel="alternate" type="text/html"/>
    <id>https://example.com/wiki/AnotherNewPost/</id>
    <published>2024-03-14T00:00:00Z</published>
    <updated>2024-03-14T00:00:00Z</updated>
    <content type="html"><![CDATA[<p>Another article...</p>]]></content>
  </entry>

  <!-- Updated pages digest (single entry) -->
  <entry>
    <title>Recently Updated Pages</title>
    <link href="https://example.com/wiki/" rel="alternate" type="text/html"/>
    <id>https://example.com/feed/updates</id>
    <updated>2024-03-15T10:30:00Z</updated>
    <content type="html"><![CDATA[
      <p>The following pages were recently updated:</p>
      <ul>
        <li><a href="https://example.com/wiki/ExistingPageA/">ExistingPageA</a> - March 15, 2024</li>
        <li><a href="https://example.com/wiki/ExistingPageB/">ExistingPageB</a> - March 13, 2024</li>
      </ul>
    ]]></content>
  </entry>
</feed>
```

### Content Handling

**For new page entries:**
- When `full_content = true`: Full HTML in `<content type="html">`
- When `full_content = false`: First paragraph or first 300 characters in `<summary>`

**For the updates digest entry:**
- Always contains a list of links with modification dates
- No full content (just the digest list)

### Empty Feed Behavior

If no pages fall within the configured `window` (no new pages AND no updated pages), **no `feed.xml` is generated**. This is intentional:

- Avoids generating empty feeds that provide no value
- Feed readers will report 404, signaling the feed is inactive
- Once new content is published, the feed reappears

If you need a feed.xml to always exist, ensure at least one page has a date within the window.

## Autodiscovery

Add a `<link>` tag to `<head>` in `layout.html` for feed autodiscovery:

```html
{% if feed_enabled %}
<link rel="alternate" type="application/atom+xml" title="{{ feed_title }}" href="{{ site_url }}/feed.xml">
{% endif %}
```

Note: Config values are flattened via `to_template_context()` before being passed to templates.

## Implementation

### Files

| File | Purpose |
|------|---------|
| `src/foliate/feed.py` | Feed generation logic, page classification, date handling |
| `src/foliate/defaults/templates/feed.xml` | Jinja2 template for Atom output |
| `src/foliate/config.py` | `FeedConfig` dataclass with defaults |
| `src/foliate/build.py` | Integration point (calls `generate_feed()`) |
| `src/foliate/defaults/templates/layout.html` | Autodiscovery `<link>` tag |

### Key Functions

- `generate_feed()` - Main entry point, orchestrates feed generation
- `classify_pages()` - Separates pages into "new" vs "updated" categories
- `get_published_date()` / `get_modified_date()` - Date resolution with fallbacks
- `generate_updates_digest()` - Creates HTML content for the digest entry

## Testing

### Unit Tests (`tests/test_feed.py`)

1. **Page classification tests**
   - New page (published within window)
   - Updated page (published before window, modified within)
   - Page outside window (neither new nor updated)
   - Page with no modification (new only)

2. **Date resolution tests**
   - Page with explicit `published` date
   - Page with `date` field
   - Page with `modified` field
   - Fallback to file timestamps

3. **Feed generation tests**
   - Valid Atom XML output
   - Correct number of new entries (respects `items` limit)
   - Updates digest contains correct pages
   - Updates digest has stable ID
   - Proper date formatting (RFC 3339)

4. **Content handling tests**
   - Full content mode
   - Summary mode

### Integration Tests

1. Full build with feed enabled
2. Build with feed disabled
3. Build with no new pages (only updates digest)
4. Build with no updates (only new pages)
5. Build with empty feed (no pages in window)

## Validation

Generated feeds should validate against:
- [W3C Feed Validation Service](https://validator.w3.org/feed/)

## Known Limitations

- **Same-day ordering**: Pages with date-only values (no time component) all normalize to midnight UTC. If multiple pages share the same date, their ordering in the feed is undefined. Add time components for precise ordering.

- **CDATA content**: Feed content uses CDATA sections. If page content contains the literal string `]]>`, it could break the XML. This is rare in practice.

- **No updates limit**: The updates digest entry has no limit on how many pages it lists. If many pages are frequently updated, the digest could become long.

## Future Considerations

Possible future enhancements:

- **Categories/tags**: Map frontmatter tags to Atom categories
- **Multiple feeds**: Per-folder or per-tag feeds
- **Custom templates**: User-overridable feed template in `.foliate/templates/`
- **JSON Feed**: Additional format (`/feed.json`) per [JSON Feed spec](https://jsonfeed.org/)
- **Per-entry author**: Support for page-specific author in frontmatter
