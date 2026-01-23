# CLAUDE.md - Foliate Project

This file provides guidance to Claude Code when working on the foliate project.

## Project Overview

**Foliate** is a static site generator that turns a markdown "vault" (a wiki-style collection of markdown files, e.g., from Obsidian) into a static HTML site.

**Key principles:**
1. **Everything in the vault** - All content, config, and output live in your vault
2. **Single executable** - One tool (`foliate`) runs inside the vault to generate website files
3. **Flexible** - Just a markdown collection as input, a website as output

```bash
cd my-vault
uvx foliate init   # Create .foliate/config.toml
uvx foliate build  # Generate site to .foliate/build/
```

## Design Philosophy

Foliate is for anyone who wants to integrate web publishing with their existing personal knowledge base. It's a more flexible and configurable alternative to Obsidian Publish or similar services.

- **Flexible theming** - Users customize via their own templates/CSS
- **Minimal opinions** - Provide structure, not style
- **Works for anyone** - A developer's notes, a researcher's wiki, a writer's blog

## Architecture

### Directory Structure (User's Vault)
```
my-vault/
├── .foliate/              # All foliate internals
│   ├── config.toml        # Site configuration
│   ├── build/             # Generated output
│   ├── cache/             # Build cache
│   ├── templates/         # Custom template overrides (optional)
│   └── static/            # Custom static assets (optional)
├── _private/              # Ignored content (configurable)
├── _homepage/             # Site root content (deployed to /)
├── assets/                # User assets (images, PDFs)
└── **/*.md                # Wiki content (deployed to /wiki/)
```

### Package Structure
```
src/foliate/
├── __init__.py
├── __main__.py            # CLI entry point
├── cli.py                 # Click CLI commands
├── build.py               # Core build logic
├── config.py              # TOML config loading
├── watch.py               # Watch mode with hot reload
├── templates.py           # Template management
├── cache.py               # Incremental build cache
├── assets.py              # Static/user asset handling
├── markdown_utils.py      # Markdown processing utilities
├── obsidian_image_size.py # Obsidian ![|width](url) syntax
├── deploy.py              # GitHub Pages deployment
├── quarto.py              # Quarto .qmd preprocessing
├── postprocess.py         # HTML post-processing (link sanitization)
└── defaults/              # Bundled defaults
    ├── templates/         # Default Jinja2 templates
    ├── static/            # Default CSS
    └── config.toml        # Default config template
```

## Core Features

### Special Directories (Underscore Convention)

| Directory | Behavior |
|-----------|----------|
| `_private/` | **Ignored** - Never built, regardless of frontmatter. Configurable via `ignored_folders` in config. |
| `_homepage/` | **Site root** - Content deployed to `/` instead of `/wiki/`. Also excluded from normal wiki generation. |

### Two-Tiered Visibility System

```yaml
---
public: true      # Required to be built at all
published: true   # Optional, shows in listings/search
---
```

- `public: false` (default) → Not built, completely private
- `public: true` → Built, accessible via direct link
- `public: true, published: true` → Built AND visible in listings

### Dual Deployment
- `_homepage/` content → Site root (`/about/`, `/projects/`)
- All other content → Wiki subdirectory (`/wiki/Home/`, `/wiki/Notes/`)

### Incremental Builds
Build cache tracks file modification times. Only changed files are rebuilt.
Config and template changes trigger automatic full rebuilds.

### Obsidian Image Syntax
Supports Obsidian-style image sizing: `![alt|width](url)` → `<img width="width">`

### Link Sanitization
Post-processing removes wikilinks to private pages, converting them to plain text.
Also cleans escaped dollar signs (`\$`) in content areas for KaTeX compatibility.

### Quarto Support
Optional preprocessing of `.qmd` files to `.md` using `quarto-prerender`.
Enabled via `[advanced] quarto_enabled = true` in config.

### Deployment
Built-in `foliate deploy` command for GitHub Pages:
- Rsyncs build output to target repository
- Commits and pushes automatically
- Supports dry-run mode

## CLI Commands

```bash
foliate init              # Create .foliate/config.toml with defaults
foliate build             # Build site to .foliate/build/
foliate build --force     # Force full rebuild
foliate build --serve     # Build and start local server
foliate watch             # Watch mode (build + serve + auto-rebuild)
foliate deploy            # Deploy to configured target (GitHub Pages)
foliate deploy --dry-run  # Preview deployment without executing
foliate clean             # Remove .foliate/build/ and .foliate/cache/
```

## Configuration

`.foliate/config.toml`:
```toml
[site]
name = "My Wiki"
url = "https://example.com"
author = "Your Name"

[build]
ignored_folders = ["_private", "drafts"]
home_redirect = "about"
wiki_prefix = "wiki"  # URL prefix for wiki content (set to "" for root)

[nav]
items = [
    { url = "/about/", label = "About" },
    { url = "/wiki/Home/", label = "Wiki" },
]

[deploy]
method = "github-pages"
target = "../my-site.github.io"  # Path to GitHub Pages repo
exclude = ["CNAME", ".gitignore", ".gitmodules", ".claude"]

[advanced]
quarto_enabled = false
quarto_python = ""  # Optional: path to Python for Quarto
```

## Development Commands

```bash
# Install in development mode
uv sync --extra dev

# Run tests
uv run pytest
# or
make test

# Run tests with coverage
uv run pytest --cov=foliate

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Build package (cleans old dist files first)
make build

# Publish to PyPI
make publish

# Test CLI locally
uv run foliate --help
```

## Dependencies

### Core
- `python-frontmatter` - YAML frontmatter parsing
- `markdown` - Markdown to HTML conversion
- `jinja2` - Template rendering
- `click` - CLI framework
- `watchdog` - File system watching
- `pygments` - Syntax highlighting
- `beautifulsoup4` - HTML post-processing

### Markdown Extensions
- `markdown-katex` - Math rendering
- `mdx-wikilink-plus` - Wiki-style links
- `mdx-linkify` - Auto-link URLs

### Optional (Quarto)
- `quarto-prerender` - Quarto .qmd preprocessing

## Key Design Decisions

1. **Single directory** - Everything in `.foliate/` keeps vaults clean
2. **TOML config** - Human-readable, no Python knowledge needed
3. **Sensible defaults** - Works out of the box with zero config
4. **Bundled templates** - Defaults packaged with the tool
5. **Override system** - Custom templates/static in `.foliate/` take precedence
6. **uvx compatible** - Runs without installation via `uvx foliate`

## Testing Strategy

- Unit tests for each module
- Integration tests for full build pipeline
- Test with real vault fixtures
- Run `uv run pytest` to verify all tests pass

## Important Notes

- Use `uv` for Python package management (not pip)
- Requires Python 3.12+
- Keep dependencies minimal
