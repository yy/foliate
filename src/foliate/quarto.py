"""Quarto preprocessing for foliate.

Converts .qmd files to .md using quarto-prerender before the main build.
"""

from pathlib import Path

from .config import Config
from .logging import debug


def preprocess_quarto(
    config: Config,
    force: bool = False,
    single_file: Path | None = None,
) -> dict[str, str]:
    """Preprocess .qmd files to .md using quarto-prerender.

    Args:
        config: Foliate configuration
        force: Force re-render all .qmd files
        single_file: Only process this specific .qmd file (Path object)

    Returns:
        dict mapping .qmd paths to generated .md paths, or empty dict if disabled/unavailable
    """
    if not config.advanced.quarto_enabled:
        return {}

    try:
        from quarto_prerender import is_quarto_available, process_all, render_qmd
    except ImportError:
        debug("quarto-prerender not installed, skipping .qmd preprocessing")
        return {}

    if not is_quarto_available():
        debug("Quarto CLI not found, skipping .qmd preprocessing")
        return {}

    vault_path = config.vault_path
    if not vault_path:
        return {}

    pages_path = vault_path.resolve()
    cache_dir = config.get_cache_dir() / "quarto"
    assets_dir = pages_path / "assets" / "quarto"

    # quarto_python is already expanded by config loading
    quarto_python = config.advanced.quarto_python or None

    if single_file:
        # Process single file
        qmd_file = Path(single_file).resolve()
        md_file = qmd_file.with_suffix(".md")

        # Check if render needed: md doesn't exist or qmd is newer
        needs_render = not md_file.exists() or (
            qmd_file.stat().st_mtime > md_file.stat().st_mtime
        )

        if force or needs_render:
            result = render_qmd(
                qmd_file=qmd_file,
                pages_dir=pages_path,
                cache_dir=cache_dir,
                assets_dir=assets_dir,
                python=quarto_python,
                verbose=False,
            )
            if result:
                return {str(qmd_file): result}
        return {}

    # Process all .qmd files
    return process_all(
        pages_dir=pages_path,
        cache_dir=cache_dir,
        assets_dir=assets_dir,
        python=quarto_python,
        force=force,
        verbose=False,
    )
