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
foliate deploy --no-build  # Deploy the existing build without rebuilding
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
foliate deploy            # Build, sync, commit, and push
foliate deploy --no-build # Skip the default build step
foliate deploy --dry-run  # Preview changes first
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
runs, including the `jupyter-cache` package.

Foliate keeps a stable execution cache for each QMD page. Editing prose still
regenerates the Markdown, but Quarto reuses Jupyter results while the executable
cells are unchanged. `foliate build --force` refreshes those results. Generated
figures are only replaced when their contents change, so unchanged images retain
their modification times. Pages containing executable inline expressions render
without Jupyter Cache because Quarto does not support that combination.

Configure in `.foliate/config.toml`:

```toml
[advanced]
quarto_enabled = true
quarto_python = ""  # Optional override; empty auto-detects the vault's .venv
```

### Publishing generated assets

Local generated figures are the default: Foliate writes them to
`assets/quarto/`, and build and deploy copy them with the rest of the site's
files. No publisher configuration is required.

Sites that do not want generated figures in Git can add
`.foliate/assets.toml`. Foliate then keeps the figures in
`.foliate/cache/quarto/assets/`. Local builds and previews remain
self-contained, while `foliate deploy` uploads only the generated figures
referenced by public pages and rewrites their URLs in a separate deployment
copy.

```toml
[publisher]
public_base_url = "https://cdn.example/site-assets"
key_prefix = "quarto"
command = [
  "aws", "s3", "sync",
  "{staging_prefix_dir}", "s3://bucket/site-assets/{key_prefix}",
  "--delete",
  "--cache-control", "no-cache",
]
```

`public_base_url` is explicit so Foliate does not have to guess how an S3 bucket
is exposed (directly, through CloudFront, or through another CDN). Each figure
has one stable object key, `{key_prefix}/{page_path}/{figure_name}`, and a later
render overwrites that object. `{staging_prefix_dir}` is the complete current
tree below `key_prefix`, allowing a scoped `sync --delete` to remove obsolete
figures without touching unrelated bucket objects. Use revalidating or short
cache headers when URLs are overwritten. `foliate deploy --dry-run` prepares
and reports the production rewrite without invoking the uploader.

The v0.8 publisher configuration and `foliate publish-assets` command are not compatible with this deployment-based workflow. Existing publisher users should follow the [v0.9 migration guide](docs/releases/0.9.0.md#migrating-the-generated-asset-publisher) before upgrading.

See the [v0.9.0 release notes](docs/releases/0.9.0.md) for the watch, Quarto, and deployment changes in this release.

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
