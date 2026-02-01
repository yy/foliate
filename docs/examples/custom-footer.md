# Customizing the Footer

This guide shows how to customize your site's footer with social links, custom text, and additional content.

## Default Footer

Foliate's default footer displays a copyright notice with the author name:

```html
<footer>
    <p class="footer-text">
        &copy; 2024 <a href="/about/">Your Name</a>
    </p>
</footer>
```

## Configuration Options

The footer is configured in `.foliate/config.toml`:

```toml
[footer]
copyright_year = 2024
author_name = "Your Name"
author_link = "about/"  # Relative path from site root
```

## Custom Footer with Social Links

Create `.foliate/templates/layout.html` and customize the footer section:

```html
<footer>
    <div class="footer-content">
        <div class="footer-social">
            <a href="https://twitter.com/yourhandle" title="Twitter">
                <svg>...</svg>
            </a>
            <a href="https://github.com/yourusername" title="GitHub">
                <svg>...</svg>
            </a>
            <a href="/feed.xml" title="RSS Feed">
                <svg>...</svg>
            </a>
        </div>
        <p class="footer-text">
            &copy; {{ footer.copyright_year }} <a href="/{{ footer.author_link }}">{{ footer.author_name }}</a>
        </p>
    </div>
</footer>
```

## Complete Footer Example

Here's a full footer with social icons (using inline SVG):

```html
<footer>
    <div class="footer-content">
        <div class="footer-social">
            <!-- Twitter/X -->
            <a href="https://twitter.com/yourhandle" title="Twitter" target="_blank" rel="noopener">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
            </a>
            <!-- GitHub -->
            <a href="https://github.com/yourusername" title="GitHub" target="_blank" rel="noopener">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
            </a>
            <!-- RSS -->
            {% if feed_enabled %}
            <a href="/feed.xml" title="RSS Feed">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19 7.38 20 6.18 20C5 20 4 19 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/>
                </svg>
            </a>
            {% endif %}
        </div>
        <p class="footer-text">
            &copy; {{ footer.copyright_year }} <a href="/{{ footer.author_link }}">{{ footer.author_name }}</a>
            · Built with <a href="https://github.com/yy/foliate">Foliate</a>
        </p>
    </div>
</footer>
```

## Footer CSS

Add these styles to `.foliate/static/main.css`:

```css
/* Enhanced Footer */
.footer-content {
    text-align: center;
}

.footer-social {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    margin-bottom: 1rem;
}

.footer-social a {
    color: var(--text-muted);
    transition: color 0.2s ease;
}

.footer-social a:hover {
    color: var(--color-primary);
}

.footer-social svg {
    display: block;
}

.footer-text {
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.footer-text a {
    color: var(--text-secondary);
}

.footer-text a:hover {
    color: var(--color-primary);
}
```

## Multi-Column Footer

For a more complex footer:

```html
<footer>
    <div class="footer-grid">
        <div class="footer-section">
            <h4>About</h4>
            <p>A personal wiki and blog about technology, research, and ideas.</p>
        </div>
        <div class="footer-section">
            <h4>Links</h4>
            <ul>
                <li><a href="/about/">About</a></li>
                <li><a href="/wiki/Home/">Wiki</a></li>
                <li><a href="/projects/">Projects</a></li>
            </ul>
        </div>
        <div class="footer-section">
            <h4>Connect</h4>
            <ul>
                <li><a href="https://twitter.com/yourhandle">Twitter</a></li>
                <li><a href="https://github.com/yourusername">GitHub</a></li>
                <li><a href="/feed.xml">RSS Feed</a></li>
            </ul>
        </div>
    </div>
    <div class="footer-bottom">
        <p>&copy; {{ footer.copyright_year }} {{ footer.author_name }}</p>
    </div>
</footer>
```

```css
/* Multi-column footer */
.footer-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 2rem;
    margin-bottom: 2rem;
    text-align: left;
}

.footer-section h4 {
    color: var(--color-primary);
    margin-bottom: 0.75rem;
    font-size: 1rem;
}

.footer-section ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.footer-section li {
    margin: 0.5rem 0;
}

.footer-section a {
    color: var(--text-secondary);
}

.footer-bottom {
    padding-top: 1rem;
    border-top: 1px solid var(--border-light);
    text-align: center;
}

@media (max-width: 768px) {
    .footer-grid {
        grid-template-columns: 1fr;
        text-align: center;
    }
}
```

## Dynamic Copyright Year

Use the current year dynamically (requires JavaScript):

```html
<p class="footer-text">
    &copy; <span id="year"></span> {{ footer.author_name }}
</p>
<script>document.getElementById('year').textContent = new Date().getFullYear();</script>
```

Or set it in your config and update annually:

```toml
[footer]
copyright_year = 2024
```
