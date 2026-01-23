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
        self.last_rebuild_time = 0.0

        # Relevant file extensions
        self.relevant_extensions = {".md", ".qmd", ".html", ".css", ".toml"} | {
            e.lower() for e in SUPPORTED_ASSET_EXTENSIONS
        }

    def on_any_event(self, event):
        if event.is_directory:
            return

        src_path = event.src_path

        # Ignore hidden files, git, and build directory
        if "/.git/" in src_path or "/.foliate/build/" in src_path:
            return

        # Check for ignored folders from config
        for folder in self.config.build.ignored_folders:
            if f"/{folder}/" in src_path:
                return

        # Check if it's a relevant file type
        ext = Path(src_path).suffix.lower()
        if ext not in self.relevant_extensions:
            return

        with self.rebuild_lock:
            if src_path not in self.pending_changes:
                self.pending_changes.append(src_path)

        # Schedule processing after debounce period
        def delayed_process():
            time.sleep(self.debounce_seconds)
            if time.time() - self.last_rebuild_time >= self.debounce_seconds:
                self.process_changes()

        threading.Thread(target=delayed_process, daemon=True).start()

    def process_changes(self):
        """Process pending file changes."""
        with self.rebuild_lock:
            if not self.pending_changes:
                return
            changes = self.pending_changes.copy()
            self.pending_changes.clear()

        # Categorize changes
        needs_full_rebuild = False
        qmd_files = []

        for file_path in changes:
            file_path = Path(file_path)
            if file_path.suffix in {".html", ".css", ".toml"}:
                needs_full_rebuild = True
            elif file_path.suffix == ".qmd":
                qmd_files.append(file_path)

        # Preprocess any changed .qmd files before rebuild
        if qmd_files and self.config.advanced.quarto_enabled:
            from .quarto import preprocess_quarto

            for qmd_file in qmd_files:
                print(f"  Preprocessing: {qmd_file.name}")
                preprocess_quarto(self.config, single_file=qmd_file)

        self.rebuild_callback(force=needs_full_rebuild)
        self.last_rebuild_time = time.time()


def watch(config: Config, port: int = 8000) -> None:
    """Start watch mode with auto-rebuild and local server.

    Args:
        config: Configuration object
        port: Port for local HTTP server
    """
    vault_path = config.vault_path
    if not vault_path:
        print("Error: No vault path configured")
        return

    print("Watch mode: Building initial site...")
    print("=" * 60)

    # Initial build
    do_build(config=config, force_rebuild=False, verbose=False)

    # Start HTTP server in background
    from .resources import start_dev_server

    build_dir = config.get_build_dir()
    server_process = start_dev_server(build_dir, port, background=True)

    print("=" * 60)
    print(f"Server started: http://localhost:{port}")
    print("Watching for changes... (Press Ctrl+C to stop)")
    print("=" * 60)

    def rebuild_callback(force: bool = False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Rebuilding...")
        start_time = time.time()
        do_build(config=config, force_rebuild=force, verbose=False)
        elapsed = time.time() - start_time
        print(f"[{timestamp}] Rebuild complete ({elapsed:.2f}s)")

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

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watch mode...")
        observer.stop()
        server_process.terminate()
        server_process.wait()
        print("Watch mode stopped.")

    observer.join()
