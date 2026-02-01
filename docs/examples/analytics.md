# Adding Analytics

This guide shows how to add analytics tracking to your Foliate site.

## Overview

Analytics scripts are typically added to the `<head>` or before `</body>` in your layout template. Create a custom `layout.html` to add your tracking code.

## Privacy Considerations

Before adding analytics, consider:

- **GDPR/Privacy compliance**: Some services require cookie consent banners
- **Privacy-focused alternatives**: Plausible, Umami, and Fathom don't use cookies
- **Self-hosted options**: Full control over your data
- **No analytics**: Many personal sites work well without tracking

## Google Analytics (GA4)

Add to `.foliate/templates/layout.html` in the `<head>` section:

```html
<head>
    <!-- ... other head content ... -->

    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-XXXXXXXXXX');
    </script>
</head>
```

Replace `G-XXXXXXXXXX` with your GA4 Measurement ID.

## Plausible Analytics (Privacy-Focused)

[Plausible](https://plausible.io) is a lightweight, privacy-focused alternative that doesn't use cookies.

Add to `<head>`:

```html
<script defer data-domain="yourdomain.com" src="https://plausible.io/js/script.js"></script>
```

### Self-hosted Plausible

```html
<script defer data-domain="yourdomain.com" src="https://analytics.yourdomain.com/js/script.js"></script>
```

## Umami (Self-Hosted)

[Umami](https://umami.is) is an open-source, privacy-focused analytics platform you can self-host.

Add to `<head>`:

```html
<script async src="https://analytics.yourdomain.com/script.js" data-website-id="your-website-id"></script>
```

## Fathom Analytics

[Fathom](https://usefathom.com) is another privacy-focused option:

```html
<script src="https://cdn.usefathom.com/script.js" data-site="ABCDEFGH" defer></script>
```

## Goat Counter (Free, Privacy-Focused)

[GoatCounter](https://www.goatcounter.com) is free for personal use:

```html
<script data-goatcounter="https://YOURCODE.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

## Complete Layout Example

Here's a complete `layout.html` with analytics:

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

    <!-- Analytics (Plausible - privacy-focused, no cookies) -->
    <script defer data-domain="yourdomain.com" src="https://plausible.io/js/script.js"></script>
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

## Environment-Based Loading

To avoid tracking in development, you can conditionally load analytics:

```html
{% if site_url and 'localhost' not in site_url %}
<script defer data-domain="yourdomain.com" src="https://plausible.io/js/script.js"></script>
{% endif %}
```

Or use the full site URL to check:

```html
{% if site_url.startswith('https://') %}
<!-- Production analytics -->
<script defer data-domain="yourdomain.com" src="https://plausible.io/js/script.js"></script>
{% endif %}
```

## Cookie Consent (for GA and similar)

If using Google Analytics or other cookie-based services in regions with GDPR/CCPA requirements, you'll need a consent banner. Here's a minimal example:

```html
<div id="cookie-banner" style="display: none; position: fixed; bottom: 0; left: 0; right: 0; padding: 1rem; background: #333; color: white; text-align: center;">
    This site uses cookies for analytics.
    <button onclick="acceptCookies()">Accept</button>
    <button onclick="declineCookies()">Decline</button>
</div>

<script>
if (!localStorage.getItem('cookies-accepted')) {
    document.getElementById('cookie-banner').style.display = 'block';
}

function acceptCookies() {
    localStorage.setItem('cookies-accepted', 'true');
    document.getElementById('cookie-banner').style.display = 'none';
    // Load analytics here
}

function declineCookies() {
    localStorage.setItem('cookies-accepted', 'false');
    document.getElementById('cookie-banner').style.display = 'none';
}
</script>
```

For a proper implementation, consider using a library like [cookieconsent](https://www.osano.com/cookieconsent).

## Comparison

| Service | Cookies | Free Tier | Self-Host | GDPR Friendly |
|---------|---------|-----------|-----------|---------------|
| Google Analytics | Yes | Yes | No | Needs consent |
| Plausible | No | Paid | Yes | Yes |
| Umami | No | Self-host | Yes | Yes |
| Fathom | No | Paid | No | Yes |
| GoatCounter | No | Yes | Yes | Yes |

For personal wikis and blogs, privacy-focused options like Plausible or GoatCounter are often the best choice.
