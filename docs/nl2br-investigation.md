# Enabling `nl2br` for Obsidian-compatible line breaks

## Problem

Foliate uses Python-Markdown without the `nl2br` extension. This means single newlines within a paragraph are collapsed into spaces — standard Markdown behavior.

Obsidian, however, treats single newlines as line breaks by default ("Strict line breaks" is off by default). This creates a rendering mismatch: content that looks correct in Obsidian (each line on its own) renders as a single run-on line on the foliate site.

### Concrete example: publication lists

In `_homepage/research.md`, publication entries look like this in the source:

```markdown
**Adaptive cut reveals multiscale complexity in networks**
Louis Boucherie, Yong-Yeol Ahn, Sune Lehmann
_Submitted_ (2025)
[arXiv](https://arxiv.org/abs/2512.08741)
```

In Obsidian, each field appears on its own line. In foliate, they collapse into one line unless the author adds trailing spaces (`  `) or backslashes (`\`) at the end of each line. Trailing spaces are invisible, fragile (editors and tools strip them), and a constant source of formatting bugs.

## Proposed solution

Add a `nl2br` config toggle in `config.toml` and conditionally enable the built-in `nl2br` Python-Markdown extension. This keeps the change user-controllable, consistent with foliate's "flexible, minimal opinions" design.

```toml
[build]
nl2br = true  # Convert single newlines to <br>, matching Obsidian's default behavior
```

## What `nl2br` does

Converts every newline character inside a block element (paragraph, list item, etc.) into a `<br>` tag. This matches Obsidian's default rendering.

Reference: https://python-markdown.github.io/extensions/nl2br/

## Risks and things to test

### Pages that may break

Any page where the author intentionally uses single newlines as "soft wraps" (expecting them to collapse into spaces) would now get unwanted `<br>` tags. This is the main risk.

Specific things to check:

1. **Long paragraphs with hard-wrapped lines** — if any `.md` files wrap prose at 80 columns using single newlines, those would now render with line breaks mid-sentence. Search for this pattern:
   ```bash
   # Find paragraphs with mid-sentence line breaks (lines that don't end with punctuation or markup)
   # -U enables multiline mode so \n matches across lines
   rg -lU '\w\n\w' --type md
   ```

2. **List items** — multi-line list items may get extra `<br>` tags. Test lists with continuation lines.

3. **Code blocks** — should be unaffected (`nl2br` only operates on block-level text, not fenced code).

4. **Interaction with `mdx-linkify`** — `nl2br` + `mdx-linkify` could theoretically interact if a URL spans a line break. Unlikely in practice but worth a quick visual check on pages with many links.

5. **Tables** — should be unaffected (processed by the `tables` extension before `nl2br`).

6. **Frontmatter** — should be unaffected (stripped by `python-frontmatter` before markdown processing).

### Testing approach

1. Build the site without `nl2br` and capture the output:
   ```bash
   cd ~/git/yyiki-pages
   uv run --project ~/git/foliate foliate build --force
   cp -r .foliate/build .foliate/build-before
   ```

2. Enable `nl2br` in foliate and rebuild:
   ```bash
   uv run --project ~/git/foliate foliate build --force
   ```

3. Diff the HTML output to see what changed:
   ```bash
   diff -rq .foliate/build-before .foliate/build
   # Then inspect specific changed files
   ```

4. Spot-check key pages:
   - `_homepage/research.md` — publication entries should now render correctly without trailing spaces
   - A few regular wiki pages with prose paragraphs — check for unwanted line breaks
   - Pages with lists, tables, code blocks — verify no regressions

### Alternative: per-page opt-in

If `nl2br` causes too many regressions globally, consider:

- A per-page frontmatter flag (e.g., `nl2br: true`) that enables the extension only for specific pages. This would require a small code change in `markdown_utils.py` to conditionally include the extension.
- Or a CSS-based approach using `white-space: pre-line` on specific sections, though this only works if the parser preserves newlines in the HTML output (it doesn't currently).

## Decision

Test globally first. If regressions are minimal and limited to a few pages that can be easily fixed, enable it globally. If regressions are widespread, implement per-page opt-in.
