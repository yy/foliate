<p align="center">
  <img src="foliate-logo-v2.png" alt="Foliate" width="400">
</p>
<p align="center">
  A static site generator for your markdown vault. A flexible, configurable alternative to Obsidian Publish.
</p>

```bash
cd my-vault
uvx foliate init    # Create .foliate/config.toml
uvx foliate build   # Generate site to .foliate/build/
uvx foliate watch   # Live preview with auto-rebuild
uvx foliate deploy  # Deploy to GitHub Pages
```

## Why Foliate?

- **Everything in your vault** - All content, config, and output stay in your vault
- **Single executable** - One tool to generate your website, no complex setup
- **Flexible** - Just markdown files in, a website out

## Features

- **Zero config** - Works out of the box with sensible defaults
- **Vault-native** - Everything lives in `.foliate/` inside your vault
- **Two-tiered visibility** - Control what's public vs. published
- **Incremental builds** - Only rebuilds changed files (auto-rebuilds on config/template changes)
- **Watch mode** - Auto-rebuild on file changes
- **Works with any markdown** - Obsidian, Logseq, or plain markdown files
- **Obsidian syntax** - Supports `![alt|width](url)` image sizing
- **Quarto support** - Preprocess `.qmd` files (optional)
- **Deploy command** - Built-in GitHub Pages deployment

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
foliate deploy    # Deploy to GitHub Pages
foliate clean     # Remove build artifacts
```

### Options

```bash
foliate build --force      # Force full rebuild
foliate build --verbose    # Detailed output
foliate build --serve      # Start server after build
foliate watch --port 3000  # Custom port
foliate deploy --dry-run   # Preview deploy without executing
foliate deploy -m "msg"    # Custom commit message
```

## Deployment

Foliate generates static files in `.foliate/build/`. Deploy anywhere that serves static files.

### GitHub Pages (Built-in)

Configure in `.foliate/config.toml`:

```toml
[deploy]
method = "github-pages"
target = "../username.github.io"  # Path to your GitHub Pages repo
exclude = ["CNAME", ".gitignore", ".gitmodules"]
```

Then deploy:

```bash
foliate deploy           # Sync, commit, and push
foliate deploy --dry-run # Preview changes first
```

### rsync (VPS/Server)
```bash
rsync -avz --delete .foliate/build/ user@server:/var/www/mysite/
```

### Simple local copy
```bash
cp -r .foliate/build/* /path/to/webserver/
```

## Customization

Foliate is designed to be customized via template and CSS overrides.

### Quick Start

```
my-vault/
└── .foliate/
    ├── templates/     # Override layout.html, page.html
    └── static/        # Override main.css, add custom assets
```

Files in these directories take precedence over Foliate's defaults.

### Documentation

See [docs/customization.md](docs/customization.md) for the full guide, including:

- Template variables reference
- CSS variables for theming
- Common customization examples:
  - [Newsletter signup forms](docs/examples/subscription-cta.md)
  - [Custom footer with social links](docs/examples/custom-footer.md)
  - [Adding analytics](docs/examples/analytics.md)
  - [Adding a sidebar](docs/examples/sidebar.md)

## Quarto Support

Foliate can preprocess `.qmd` files (Quarto markdown) to `.md` before building.
Install the [Quarto CLI](https://quarto.org/docs/get-started/) separately. Python
documents also need a working Jupyter kernel in the environment where Foliate
runs.

Configure in `.foliate/config.toml`:

```toml
[advanced]
quarto_enabled = true
quarto_python = ""  # Optional override; empty auto-detects the vault's .venv
```

### Publishing generated assets

QMD pages can keep rendered figures in ignored draft storage and publish them through a configurable command adapter. Opt a page in with `publish_assets: true`, then configure `.foliate/assets.toml`:

```toml
[publisher]
command = ["aws", "s3", "cp", "{source}", "s3://bucket/{key}"]
url_template = "https://cdn.example/{key}"
key_template = "{page_slug}/{filename}"
draft_root = "assets/drafts/quarto"
manifest = ".foliate/published-assets.json"
```

Normal build and watch commands never invoke the uploader. To set the page's `published` field and publish its assets as one step, run:

```bash
foliate publish-assets "Page.qmd" --set-published
```

The command sets `published: true` before it invokes the uploader and restores the original source if rendering or upload fails. It force-renders the page, uploads changed files, records their hashes and public URLs in the manifest, rewrites the cached Markdown, and removes the local draft directory. Without `--set-published`, it refuses an unpublished page. A later build fails if a rendered asset differs from its manifest entry; run `publish-assets` again to update it. Use `--dry-run` to render and report the pending uploads without invoking the command adapter or retaining the frontmatter change.

## Development / CI

Foliate uses a cross-platform GitHub Actions CI workflow on pull requests and `main` pushes:

- Test matrix: Linux, macOS, Windows on Python 3.12 and 3.13
- Build + smoke matrix: Linux, macOS, Windows (Python 3.13), including wheel install and CLI smoke checks

Releases remain manual via:

```bash
make publish
```

For the complete maintainer release process, see [docs/releasing.md](docs/releasing.md).

## License

MIT
