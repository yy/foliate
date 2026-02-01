# Adding a Newsletter Signup

This guide shows how to add a newsletter subscription form to your Foliate site.

## Overview

We'll add a call-to-action (CTA) section that appears at the bottom of wiki pages, inviting readers to subscribe to your newsletter.

## Step 1: Create the Template Override

Create `.foliate/templates/layout.html` with your subscription section. Here's a complete example:

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

    <article>
        {% block content %}{% endblock %}
    </article>

    <!-- Newsletter CTA - only on wiki pages -->
    {% if page and page.url.startswith('/wiki/') %}
    <section class="subscribe-cta">
        <h3>Stay Updated</h3>
        <p>Get new posts delivered to your inbox.</p>
        <a href="/subscribe/" class="subscribe-button">Subscribe</a>
    </section>
    {% endif %}

    <div class="footer-separator"></div>

    <footer>
        <p class="footer-text">
            {% if footer.author_name %}
            &copy; {{ footer.copyright_year }} <a href="/{{ footer.author_link }}">{{ footer.author_name }}</a>
            {% else %}
            &copy; {{ footer.copyright_year }}
            {% endif %}
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

## Step 2: Add CSS Styling

Add styles to `.foliate/static/main.css` (or create a new file and import it):

```css
/* Newsletter CTA Section */
.subscribe-cta {
    margin: 3rem 0 2rem 0;
    padding: 2rem;
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border-radius: 8px;
    text-align: center;
    border: 1px solid var(--border-light);
}

.subscribe-cta h3 {
    margin: 0 0 0.5rem 0;
    color: var(--color-primary);
    font-size: 1.3rem;
}

.subscribe-cta p {
    margin: 0 0 1.5rem 0;
    color: var(--text-secondary);
}

.subscribe-button {
    display: inline-block;
    padding: 0.75rem 2rem;
    background: var(--color-primary);
    color: white !important;
    text-decoration: none;
    border-radius: 6px;
    font-weight: 600;
    transition: background 0.2s ease;
}

.subscribe-button:hover {
    background: var(--color-primary-dark);
    text-decoration: none !important;
}
```

## Step 3: Create a Subscribe Page

Create `_homepage/subscribe.md` for a dedicated subscription page:

```markdown
---
public: true
title: Subscribe
description: Subscribe to my newsletter for updates
---

# Subscribe

Get new posts and updates delivered to your inbox.

<!-- Buttondown embed -->
<form
  action="https://buttondown.com/api/emails/embed-subscribe/YOUR_USERNAME"
  method="post"
  target="popupwindow"
  class="embeddable-buttondown-form"
>
  <input type="email" name="email" placeholder="your@email.com" required />
  <button type="submit">Subscribe</button>
</form>
```

## Email Service Embeds

### Buttondown

```html
<form
  action="https://buttondown.com/api/emails/embed-subscribe/YOUR_USERNAME"
  method="post"
  target="popupwindow"
  class="embeddable-buttondown-form"
>
  <input type="email" name="email" placeholder="your@email.com" required />
  <button type="submit">Subscribe</button>
</form>
```

### Mailchimp

```html
<form
  action="https://YOUR_DOMAIN.us1.list-manage.com/subscribe/post?u=XXXXX&amp;id=XXXXX"
  method="post"
  target="_blank"
>
  <input type="email" name="EMAIL" placeholder="your@email.com" required />
  <button type="submit">Subscribe</button>
</form>
```

### ConvertKit

```html
<form
  action="https://app.convertkit.com/forms/FORM_ID/subscriptions"
  method="post"
>
  <input type="email" name="email_address" placeholder="your@email.com" required />
  <button type="submit">Subscribe</button>
</form>
```

### Substack

For Substack, you'll typically link to your Substack page rather than embedding:

```html
<a href="https://YOUR_PUBLICATION.substack.com/subscribe" class="subscribe-button">
  Subscribe on Substack
</a>
```

## Form Styling

Style your embedded forms consistently:

```css
/* Email form styling */
.subscribe-cta form {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    flex-wrap: wrap;
}

.subscribe-cta input[type="email"] {
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-medium);
    border-radius: 6px;
    font-size: 1rem;
    min-width: 250px;
}

.subscribe-cta input[type="email"]:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px rgba(35, 45, 75, 0.1);
}

.subscribe-cta button[type="submit"] {
    padding: 0.75rem 1.5rem;
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s ease;
}

.subscribe-cta button[type="submit"]:hover {
    background: var(--color-primary-dark);
}
```

## Conditional Display

### Show only on specific pages

Using frontmatter to control display:

```yaml
---
public: true
show_subscribe: true
---
```

```jinja2
{% if page.meta.show_subscribe %}
<section class="subscribe-cta">
    ...
</section>
{% endif %}
```

### Hide on specific pages

```yaml
---
public: true
hide_subscribe: true
---
```

```jinja2
{% if page.url.startswith('/wiki/') and not page.meta.hide_subscribe %}
<section class="subscribe-cta">
    ...
</section>
{% endif %}
```

## Alternative: Inline CTA

Instead of a layout-level CTA, add it directly in markdown using HTML:

```markdown
---
public: true
published: true
---

# My Article

Article content here...

<div class="subscribe-cta">
  <h3>Enjoyed this post?</h3>
  <p>Subscribe for more like this.</p>
  <a href="/subscribe/" class="subscribe-button">Subscribe</a>
</div>
```

This gives per-page control without template modifications.
