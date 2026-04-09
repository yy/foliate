"""Watch mode for foliate - auto-rebuild on file changes."""

import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .assets import SUPPORTED_ASSET_EXTENSIONS
from .build import build as do_build
from .config import Config


class FoliateEventHandler(FileSystemEventHandler):
    """Handle file system events for foliate watch mode."""

    _IGNORED_PATH_MARKERS = ("/.git/", "/.foliate/build/", "/.foliate/cache/")
    _FULL_REBUILD_EXTENSIONS = {".html", ".css", ".toml"}

    def __init__(
        self,
        config: Config,
        rebuild_callback,
        debounce_seconds: float = 0.2,
    ):
        super().__init__()
        self.config = config
        self.rebuild_callback = rebuild_callback
        self.debounce_seconds = debounce_seconds
        self.pending_changes: list[str] = []
        self.rebuild_lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None

        # Relevant file extensions
        self.relevant_extensions = {".md", ".qmd", ".html", ".css", ".toml"} | {
            e.lower() for e in SUPPORTED_ASSET_EXTENSIONS
        }

    def _normalize_path(self, path: str) -> str:
        return path.replace("\\", "/")

    def _get_relative_path_parts(self, normalized_path: str) -> list[str]:
        relative_path = normalized_path.lstrip("/")
        if self.config.vault_path:
            prefix = self._normalize_path(str(self.config.vault_path)).rstrip("/") + "/"
            if normalized_path.startswith(prefix):
                relative_path = normalized_path[len(prefix) :]
        return [part for part in relative_path.split("/") if part]

    def _should_ignore_path(self, normalized_path: str) -> bool:
        if any(marker in normalized_path for marker in self._IGNORED_PATH_MARKERS):
            return True

        path_parts = self._get_relative_path_parts(normalized_path)
        return any(
            folder in path_parts[:-1] for folder in self.config.build.ignored_folders
        )

    def _should_track_path(self, src_path: str) -> bool:
        return Path(src_path).suffix.lower() in self.relevant_extensions

    def _iter_event_paths(self, event) -> list[str]:
        """Return the path(s) that should trigger a rebuild for an event."""
        src_path = event.src_path
        dest_path = getattr(event, "dest_path", "")

        if not dest_path:
            return [src_path]

        normalized_src = self._normalize_path(src_path)
        normalized_dest = self._normalize_path(dest_path)

        src_is_relevant = not self._should_ignore_path(
            normalized_src
        ) and self._should_track_path(src_path)
        dest_is_relevant = not self._should_ignore_path(
            normalized_dest
        ) and self._should_track_path(dest_path)

        if dest_is_relevant:
            return [dest_path]
        if src_is_relevant:
            return [src_path]
        return []

    def _queue_change(self, src_path: str) -> None:
        with self.rebuild_lock:
            if src_path not in self.pending_changes:
                self.pending_changes.append(src_path)

            # Cancel existing timer and start a new one (debounce reset)
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self.debounce_seconds, self.process_changes
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _take_pending_changes(self) -> list[str]:
        with self.rebuild_lock:
            if not self.pending_changes:
                return []
            changes = self.pending_changes.copy()
            self.pending_changes.clear()
        return changes

    def _categorize_changes(self, changes: list[str]) -> tuple[bool, list[Path]]:
        needs_full_rebuild = False
        qmd_files: list[Path] = []

        for changed_path in changes:
            path = Path(changed_path)
            suffix = path.suffix.lower()
            if suffix in self._FULL_REBUILD_EXTENSIONS:
                needs_full_rebuild = True
            elif suffix == ".qmd":
                qmd_files.append(path)

        return needs_full_rebuild, qmd_files

    def on_any_event(self, event):
        if event.is_directory:
            return

        for event_path in self._iter_event_paths(event):
            normalized_path = self._normalize_path(event_path)

            if self._should_ignore_path(normalized_path):
                continue

            if not self._should_track_path(event_path):
                continue

            self._queue_change(event_path)

    def process_changes(self):
        """Process pending file changes."""
        changes = self._take_pending_changes()
        if not changes:
            return

        needs_full_rebuild, qmd_files = self._categorize_changes(changes)

        # Preprocess any changed .qmd files before rebuild
        if qmd_files and self.config.advanced.quarto_enabled:
            from .logging import info
            from .quarto import preprocess_quarto

            for qmd_file in qmd_files:
                info(f"  Preprocessing: {qmd_file.name}")
                preprocess_quarto(self.config, single_file=qmd_file)

        self.rebuild_callback(force=needs_full_rebuild)


def watch(config: Config, port: int = 8000, verbose: bool = False) -> None:
    """Start watch mode with auto-rebuild and local server.

    Args:
        config: Configuration object
        port: Port for local HTTP server
        verbose: Enable verbose output
    """
    from .logging import error, info, setup_logging

    # Initialize logging for watch mode
    setup_logging(verbose=verbose)

    vault_path = config.vault_path
    if not vault_path:
        error("No vault path configured")
        return

    info("Watch mode: Building initial site...")
    info("=" * 60)

    # Initial build from source to avoid stale post-processed HTML from prior runs.
    do_build(config=config, force_rebuild=True)

    # Start HTTP server in background
    from .resources import start_dev_server

    build_dir = config.get_build_dir()
    server_process = None
    try:
        server_process = start_dev_server(build_dir, port, background=True)
        info("=" * 60)
        info(f"Server started: http://localhost:{port}")
    except OSError as e:
        error(f"Could not start server: {e}")
        info("=" * 60)
        info("Continuing in watch-only mode (no server)")

    info("Watching for changes... (Press Ctrl+C to stop)")
    info("=" * 60)

    rebuild_lock = threading.Lock()
    _pending = False
    _pending_force = False

    def rebuild_callback(force: bool = False):
        nonlocal _pending, _pending_force
        if not rebuild_lock.acquire(blocking=False):
            _pending = True
            if force:
                _pending_force = True
            return
        try:
            while True:
                if _pending_force:
                    force = True
                _pending = False
                _pending_force = False

                timestamp = datetime.now().strftime("%H:%M:%S")
                info(f"\n[{timestamp}] Rebuilding...")
                start_time = time.time()
                do_build(config=config, force_rebuild=force)
                elapsed = time.time() - start_time
                info(f"[{timestamp}] Rebuild complete ({elapsed:.2f}s)")

                if not _pending:
                    break
                force = False
        finally:
            rebuild_lock.release()

    # Setup watchdog
    handler = FoliateEventHandler(config, rebuild_callback)
    observer = Observer()

    # Watch the vault directory
    observer.schedule(handler, str(vault_path), recursive=True)

    # Also watch .foliate/templates and .foliate/static if they exist
    templates_dir = vault_path / ".foliate" / "templates"
    static_dir = vault_path / ".foliate" / "static"

    if templates_dir.exists():
        observer.schedule(handler, str(templates_dir), recursive=True)
    if static_dir.exists():
        observer.schedule(handler, str(static_dir), recursive=True)

    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        info("\nStopping watch mode...")
    finally:
        observer.stop()
        if server_process:
            server_process.terminate()
            server_process.wait()
        try:
            observer.join()
        except RuntimeError:
            pass
        info("Watch mode stopped.")
