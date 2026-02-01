# Adding a Sidebar

This guide shows how to add a sidebar to your Foliate site, including a table of contents or related pages widget.

## Overview

Adding a sidebar requires modifying both the layout template and CSS to create a two-column layout.

## Basic Sidebar Layout

### Step 1: Update layout.html

Create `.foliate/templates/layout.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}{{ site_name }}{% endblock %}</title>

    {% if page and page.description %}
    <meta name="description" content="{{ page.description }}">
    {% endif %}

    <link rel="stylesheet" type="text/css" href="/static/main.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.css">

    {% if feed_enabled %}
    <link rel="alternate" type="application/atom+xml" title="{{ feed_title or site_name }}" href="{{ site_url }}/feed.xml">
    {% endif %}
</head>
<body>
    <nav class="top-nav">
        {% for nav_item in header_nav %}
            {% if not loop.first %}<span class="nav-separator">·</span>{% endif %}
            <a href="{{ nav_item.url }}">{{ nav_item.label }}</a>
        {% endfor %}
    </nav>

    <div class="page-layout">
        <article class="main-content">
            {% block content %}{% endblock %}
        </article>

        <aside class="sidebar">
            {% block sidebar %}
            <div class="sidebar-section">
                <h4>Navigation</h4>
                <ul>
                    <li><a href="/wiki/Home/">Home</a></li>
                    <li><a href="/about/">About</a></li>
                </ul>
            </div>
            {% endblock %}
        </aside>
    </div>

    <div class="footer-separator"></div>

    <footer>
        <p class="footer-text">
            &copy; {{ footer.copyright_year }} <a href="/{{ footer.author_link }}">{{ footer.author_name }}</a>
        </p>
    </footer>

    <!-- KaTeX for math rendering -->
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/contrib/auto-render.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false}
                ],
                throwOnError: false
            });
        });
    </script>
</body>
</html>
```

### Step 2: Add Sidebar CSS

Add to `.foliate/static/main.css`:

```css
/* Two-column layout */
.page-layout {
    display: grid;
    grid-template-columns: 1fr 250px;
    gap: 3rem;
    max-width: 1100px;
    margin: 0 auto;
}

.main-content {
    min-width: 0; /* Prevent overflow */
}

/* Sidebar styles */
.sidebar {
    padding-top: 3rem;
}

.sidebar-section {
    margin-bottom: 2rem;
}

.sidebar-section h4 {
    color: var(--color-primary);
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-light);
}

.sidebar-section ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.sidebar-section li {
    margin: 0.5rem 0;
}

.sidebar-section a {
    color: var(--text-secondary);
    font-size: 0.95rem;
}

.sidebar-section a:hover {
    color: var(--color-primary);
}

/* Responsive: stack on mobile */
@media (max-width: 900px) {
    .page-layout {
        grid-template-columns: 1fr;
    }

    .sidebar {
        padding-top: 2rem;
        border-top: 1px solid var(--border-light);
    }
}
```

## Table of Contents Sidebar

Add a table of contents generated from page headings using JavaScript:

```html
<aside class="sidebar">
    <div class="sidebar-section toc">
        <h4>On This Page</h4>
        <nav id="toc"></nav>
    </div>
</aside>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const toc = document.getElementById('toc');
    const headings = document.querySelectorAll('.main-content h2, .main-content h3');

    if (headings.length < 2) {
        // Hide TOC if fewer than 2 headings
        toc.parentElement.style.display = 'none';
        return;
    }

    const list = document.createElement('ul');

    headings.forEach(function(heading) {
        // Ensure heading has an ID
        if (!heading.id) {
            heading.id = heading.textContent.toLowerCase()
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/(^-|-$)/g, '');
        }

        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = '#' + heading.id;
        a.textContent = heading.textContent.replace('¶', '').trim();

        // Indent h3s
        if (heading.tagName === 'H3') {
            li.style.paddingLeft = '1rem';
        }

        li.appendChild(a);
        list.appendChild(li);
    });

    toc.appendChild(list);
});
</script>
```

### TOC CSS

```css
/* Table of Contents */
.toc ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.toc li {
    margin: 0.4rem 0;
}

.toc a {
    color: var(--text-muted);
    font-size: 0.85rem;
    line-height: 1.4;
    display: block;
}

.toc a:hover {
    color: var(--color-primary);
}

/* Active heading highlight (optional) */
.toc a.active {
    color: var(--color-primary);
    font-weight: 500;
}
```

## Sticky Sidebar

Make the sidebar stick while scrolling:

```css
.sidebar {
    position: sticky;
    top: 2rem;
    height: fit-content;
    max-height: calc(100vh - 4rem);
    overflow-y: auto;
}
```

## Related Pages Widget

Show related pages based on tags:

```html
{% if page.tags %}
<div class="sidebar-section">
    <h4>Related Topics</h4>
    <div class="tag-list">
        {% for tag in page.tags %}
        <span class="tag">{{ tag }}</span>
        {% endfor %}
    </div>
</div>
{% endif %}
```

```css
.tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.tag {
    background: var(--background-code);
    color: var(--text-secondary);
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.8rem;
}
```

## Conditional Sidebar

Show sidebar only on wiki pages:

```html
<div class="page-layout {% if not page.url.startswith('/wiki/') %}no-sidebar{% endif %}">
    <article class="main-content">
        {% block content %}{% endblock %}
    </article>

    {% if page.url.startswith('/wiki/') %}
    <aside class="sidebar">
        <!-- Sidebar content -->
    </aside>
    {% endif %}
</div>
```

```css
.page-layout.no-sidebar {
    grid-template-columns: 1fr;
    max-width: 800px;
}
```

## Left Sidebar Variant

Put the sidebar on the left:

```css
.page-layout {
    grid-template-columns: 250px 1fr;
}
```

Or switch order in HTML:

```html
<div class="page-layout">
    <aside class="sidebar">...</aside>
    <article class="main-content">...</article>
</div>
```

## Both Sidebars

For documentation-style layouts with left navigation and right TOC:

```html
<div class="page-layout three-column">
    <aside class="sidebar-left">
        <h4>Navigation</h4>
        <!-- Navigation tree -->
    </aside>

    <article class="main-content">
        {% block content %}{% endblock %}
    </article>

    <aside class="sidebar-right">
        <h4>On This Page</h4>
        <!-- Table of contents -->
    </aside>
</div>
```

```css
.three-column {
    grid-template-columns: 200px 1fr 200px;
    max-width: 1300px;
}

@media (max-width: 1100px) {
    .three-column {
        grid-template-columns: 1fr;
    }

    .sidebar-left {
        order: 2;
    }

    .sidebar-right {
        order: 3;
    }
}
```
