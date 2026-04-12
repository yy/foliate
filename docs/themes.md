# Theme System Design

Status: **design phase** — not yet implemented.

## Problem

Users must create their own CSS and templates from scratch. The existing
customization docs explain *how* to override, but offer no starting points
beyond the single bundled default. This is the most common friction point
reported about foliate.

## Current architecture

- One bundled default: `defaults/templates/` + `defaults/static/main.css`
- CSS uses 13 custom properties (colors) and 3 font-family variables
- Override precedence: `.foliate/templates/` > bundled, `.foliate/static/` > bundled
- Template loader: Jinja2 `ChoiceLoader` (FileSystem → Package)

## Design constraints

- Themes must not complicate the zero-config happy path (`foliate build` still works)
- A vault with no `theme` key behaves exactly as today (backward compatible)
- Users can always override individual files on top of any theme
- Themes should be portable — a theme that works for one vault works for another

---

## Option A: CSS-only presets

A theme is a `:root {}` block that overrides CSS custom properties. No template
changes — all presets share the same layout.

### Config

```toml
[site]
theme = "academic"  # "default" | "academic" | "minimal" | "garden"
```

### File layout

```
src/foliate/
└── defaults/
    └── themes/
        ├── default.css    # current main.css variables (identity)
        ├── academic.css   # serif-forward, muted tones
        ├── minimal.css    # monochrome, tight spacing
        └── garden.css     # warm, wiki/zettelkasten feel
```

Each file is just a `:root { ... }` block (+ optional dark mode media query).
At build time, the selected preset's variables are prepended to `main.css`, or
loaded as a separate `<link>` before `main.css`.

### Precedence

1. User's `.foliate/static/main.css` (full override, as today)
2. Selected theme preset CSS variables
3. Bundled `main.css` base styles

### Pros

- Trivial to implement (one afternoon)
- No new abstractions — themes are just CSS files
- Easy to contribute new presets
- No maintenance surface for template compatibility

### Cons

- Limited to color/font/spacing variations on the same layout
- Can't change nav structure, page layout, or add components

---

## Option B: Theme packages (templates + CSS)

A theme is a directory containing templates, static assets, and a manifest.

### Config

```toml
[site]
theme = "academic"                # bundled theme
# theme = "foliate-theme-tufte"   # installed Python package
# theme = ".foliate/themes/mine"  # local directory
```

### Theme directory structure

```
academic/
├── theme.toml         # manifest: name, description, variables
├── templates/
│   ├── layout.html
│   └── page.html
└── static/
    └── main.css
```

### Resolution order

1. User overrides (`.foliate/templates/`, `.foliate/static/`)
2. Active theme's templates/static
3. Bundled defaults

The Jinja2 `ChoiceLoader` gains a middle layer.

### Manifest (`theme.toml`)

```toml
[theme]
name = "Academic"
description = "Serif typography, footnotes, citation styling"
foliate_version = ">=0.8"

[variables]
# Declared so `foliate init --theme academic` can scaffold config
color_primary = "#1a365d"
font_family_serif = "Palatino, Georgia, serif"
```

### Distribution

| Source | Resolution |
|--------|-----------|
| Bundled | `src/foliate/themes/{name}/` |
| PyPI package | `importlib.metadata` entry point `foliate.themes` |
| Local path | Relative to vault root |

### Pros

- Real visual variety (different layouts, not just colors)
- Composable — users override individual templates from any theme
- Familiar pattern (Hugo, Jekyll, Eleventy)

### Cons

- Template API becomes a compatibility surface
- Theme authors need to track template variable changes across versions
- More complex loader logic

---

## Option C: Plugin system (themes + build hooks)

Everything in Option B, plus a hook system for extending the build pipeline:
custom Markdown extensions, extra template context, new CLI subcommands.

**Not recommended now.** Plugin APIs are hard to design upfront and easy to add
once real extension needs emerge. Defer until Option B is stable and users ask
for specific hooks.

---

## Recommendation

**Ship Option A now, design toward Option B.**

1. Add 3–4 CSS presets with the `theme` config key.
2. Structure the preset loader so it naturally extends to full theme
   directories later — same config key, same resolution logic.
3. Revisit Option B when users want layout-level changes.

### Candidate presets

| Name | Character |
|------|-----------|
| `default` | Current look (blue primary, Inter/sans, clean) |
| `academic` | Serif body, muted blues/grays, wider measure, footnote-friendly |
| `minimal` | System font stack, monochrome, tight spacing, no accent color |
| `garden` | Warm palette (greens/amber), slightly rounded, wiki/garden feel |

### Migration path A → B

The `theme = "academic"` key resolves to a CSS file in Option A and to a full
theme directory in Option B. The resolution logic checks:

1. Is it a local path with `theme.toml`? → full theme
2. Is it an installed package? → full theme
3. Is it a name matching `defaults/themes/{name}.css`? → CSS preset

This means Option A themes continue to work after Option B is added.
