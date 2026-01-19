# Foliate

A static site generator for your markdown vault. A flexible, configurable alternative to Obsidian Publish.

```bash
cd my-vault
uvx foliate init   # Create .foliate/config.toml
uvx foliate build  # Generate site to .foliate/build/
```

## Why Foliate?

- **Everything in your vault** - All content, config, and output stay in your vault
- **Single executable** - One tool to generate your website, no complex setup
- **Flexible** - Just markdown files in, a website out

## Features

- **Zero config** - Works out of the box with sensible defaults
- **Vault-native** - Everything lives in `.foliate/` inside your vault
- **Two-tiered visibility** - Control what's public vs. published
- **Incremental builds** - Only rebuilds changed files
- **Watch mode** - Auto-rebuild on file changes
- **Works with any markdown** - Obsidian, Logseq, or plain markdown files

## Quick Start

```bash
# Initialize in your vault
cd my-vault
uvx foliate init

# Build
uvx foliate build

# Watch mode (build + serve + auto-rebuild)
uvx foliate watch
```

## Directory Structure

```
my-vault/
├── .foliate/
│   ├── config.toml      # Configuration
│   ├── build/           # Generated site
│   ├── cache/           # Build cache
│   ├── templates/       # Custom templates (optional)
│   └── static/          # Custom CSS/JS (optional)
├── _private/            # Ignored - never built
├── _homepage/           # Site root (/, /about/, etc.)
│   └── about.md         # → example.com/about/
├── assets/              # Images, PDFs
├── Home.md              # → example.com/wiki/Home/
└── Notes/
    └── ideas.md         # → example.com/wiki/Notes/ideas/
```

### Special Directories

| Directory | Purpose |
|-----------|---------|
| `_private/` | Never built, regardless of frontmatter. Configurable via `ignored_folders` in config. |
| `_homepage/` | Content deployed to site root (`/`) instead of `/wiki/` (or other prefix). Excluded from normal wiki generation. |

## Visibility System

Control what gets built and listed:

```yaml
---
public: true       # Built and accessible via direct link
published: true    # Also appears in listings and search
---
```

- No frontmatter or `public: false` → Not built (private)
- `public: true` → Built, accessible via URL
- `public: true, published: true` → Built AND visible in listings

## Configuration

`.foliate/config.toml`:

```toml
[site]
name = "My Wiki"
url = "https://example.com"

[build]
ignored_folders = ["_private", "drafts"]
wiki_prefix = "wiki"  # URL prefix for wiki content (set to "" for root)

[nav]
items = [
    { url = "/about/", label = "About" },
    { url = "/wiki/Home/", label = "Wiki" },
]
```

## Commands

```bash
foliate init      # Create .foliate/config.toml
foliate build     # Build site
foliate watch     # Build + serve + auto-rebuild
foliate clean     # Remove build artifacts
```

### Options

```bash
foliate build --force     # Force full rebuild
foliate build --verbose   # Detailed output
foliate build --serve     # Start server after build
foliate watch --port 3000 # Custom port
```

## Deployment

Foliate generates static files in `.foliate/build/`. Deploy anywhere that serves static files:

### rsync (VPS/Server)
```bash
rsync -avz --delete .foliate/build/ user@server:/var/www/mysite/
```

### GitHub Pages

**Separate repo** - e.g., push to a dedicated `username.github.io` repo:

```bash
# Clone your GitHub Pages repo alongside your vault
git clone git@github.com:username/username.github.io.git ../username.github.io

# Copy build output and push
cp -r .foliate/build/* ../username.github.io/
cd ../username.github.io && git add . && git commit -m "Deploy" && git push
```

**Same repo** - If your vault is the GitHub Pages repo:

```bash
# Option 1: Use docs/ folder (configure GitHub Pages to serve from docs/)
cp -r .foliate/build/* docs/

# Option 2: Use gh-pages branch (requires Node.js)
npx gh-pages -d .foliate/build
```

### Simple local copy
```bash
cp -r .foliate/build/* /path/to/webserver/
```

## License

MIT
