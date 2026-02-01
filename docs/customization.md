# Customizing Foliate

Foliate is designed to be customized. This guide covers how to override templates, add custom CSS, and extend your site's functionality.

## How Customization Works

Foliate uses a two-tier override system:

1. **Default templates/assets** are bundled with Foliate
2. **Your overrides** in `.foliate/templates/` and `.foliate/static/` take precedence

When Foliate builds your site, it checks for custom versions first. If found, it uses yours; otherwise, it falls back to the defaults.

## Template Overrides

### Directory Structure

```
my-vault/
└── .foliate/
    └── templates/
        ├── layout.html    # Base layout (nav, footer, scripts)
        └── page.html      # Individual page template
```

### Creating an Override

1. Copy the default template you want to modify:
   ```bash
   # Find where foliate is installed
   python -c "import foliate; print(foliate.__path__[0])"

   # Or just create from scratch using the examples below
   ```

2. Place your modified version in `.foliate/templates/`

3. Run `foliate build` - your template will be used automatically

### Template Inheritance

Templates use Jinja2 inheritance. The default structure is:

- `layout.html` - Base layout with `<head>`, navigation, footer, and scripts
- `page.html` - Extends `layout.html`, adds content structure

You can override just `page.html` to change content presentation while keeping the base layout, or override `layout.html` for full control.

## Static Asset Overrides

### Directory Structure

```
my-vault/
└── .foliate/
    └── static/
        └── main.css    # Custom stylesheet
```

### Custom CSS

Create `.foliate/static/main.css` to completely replace the default stylesheet, or create additional CSS files and reference them in your custom `layout.html`.

## Template Variables Reference

These variables are available in all templates:

### Site Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `site_name` | Site name from config | `"My Wiki"` |
| `site_url` | Full site URL | `"https://example.com"` |
| `default_og_image` | Default social preview image | `"/assets/images/preview.png"` |

### Navigation

| Variable | Description |
|----------|-------------|
| `header_nav` | List of nav items: `{url, label, logo?, logo_alt?}` |

### Footer

| Variable | Description |
|----------|-------------|
| `footer.author_name` | Author name for copyright |
| `footer.author_link` | Link to author page |
| `footer.copyright_year` | Copyright year |

### Feed

| Variable | Description |
|----------|-------------|
| `feed_enabled` | Whether Atom feed is enabled |
| `feed_title` | Feed title |

### Page Variables (in page templates)

| Variable | Description | Example |
|----------|-------------|---------|
| `page.title` | Page title from frontmatter | `"My Page"` |
| `page.path` | Page path (filename without extension) | `"Notes/ideas"` |
| `page.url` | Full URL path | `"/wiki/Notes/ideas/"` |
| `page.description` | Description from frontmatter or auto-extracted | |
| `page.image` | Featured image URL | |
| `page.date` | Publication date from frontmatter | |
| `page.file_modified` | File modification date | `"2024-01-15"` |
| `page.published` | Whether page is published (visible in listings) | |
| `page.tags` | List of tags from frontmatter | |
| `page.meta` | Full frontmatter dict (access any custom field) | |
| `content` | Rendered HTML content (use with `\|safe` filter) | |
| `base_url` | Base URL for this content type | `"/wiki/"` or `"/"` |

### Home Page Variables

| Variable | Description |
|----------|-------------|
| `home_page` | Name of home page (e.g., `"Home"`) |
| `recent_pages` | List of recently modified published pages (on home page only) |

## CSS Variables

The default stylesheet uses CSS custom properties for easy theming. Override these in your custom CSS:

```css
:root {
  /* Primary Colors */
  --color-primary: #232D4B;
  --color-primary-dark: #133584;
  --color-secondary: #7c3aed;
  --color-accent: #f59e0b;

  /* Typography */
  --font-family-sans: "Inter", -apple-system, sans-serif;
  --font-family-mono: ui-monospace, Menlo, monospace;
  --font-family-serif: Palatino, Georgia, serif;

  /* Neutral Colors */
  --text-primary: #111827;
  --text-secondary: #4b5563;
  --text-muted: #9ca3af;
  --background-primary: #ffffff;
  --background-code: #f3f4f6;
  --border-light: #e5e7eb;
  --border-medium: #d1d5db;
}
```

### Quick Theme Example

To create a dark theme, add this to `.foliate/static/main.css`:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --text-primary: #f3f4f6;
    --text-secondary: #d1d5db;
    --text-muted: #9ca3af;
    --background-primary: #111827;
    --background-code: #1f2937;
    --border-light: #374151;
    --border-medium: #4b5563;
  }
}
```

## Common Customization Examples

See the [examples](examples/) folder for detailed guides:

- [Adding a Newsletter Signup](examples/subscription-cta.md) - Add Buttondown, Mailchimp, or ConvertKit
- [Customizing the Footer](examples/custom-footer.md) - Social links, copyright text
- [Adding Analytics](examples/analytics.md) - Google Analytics, Plausible, Umami
- [Adding a Sidebar](examples/sidebar.md) - Table of contents, related pages

## Tips

### Conditional Content by URL

Show content only on wiki pages (not homepage content):

```jinja2
{% if page.url.startswith('/wiki/') %}
  <!-- Wiki-only content here -->
{% endif %}
```

### Accessing Custom Frontmatter

Any frontmatter field is accessible via `page.meta`:

```yaml
---
public: true
custom_field: "my value"
show_cta: true
---
```

```jinja2
{% if page.meta.show_cta %}
  <!-- Show call-to-action -->
{% endif %}

<p>Custom: {{ page.meta.custom_field }}</p>
```

### Safe HTML Output

Always use the `|safe` filter when outputting HTML content:

```jinja2
{{ content|safe }}
```

### Build Cache

Template changes automatically trigger a full rebuild. If you're making rapid changes, use `--force` to ensure a clean build:

```bash
foliate build --force
```
