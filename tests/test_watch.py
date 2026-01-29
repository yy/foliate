"""Tests for watch mode functionality."""

import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from watchdog.events import DirCreatedEvent, FileModifiedEvent

from foliate.config import Config
from foliate.watch import FoliateEventHandler, watch


class TestFoliateEventHandler:
    """Tests for FoliateEventHandler class."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a minimal config for testing."""
        config = Config()
        config.vault_path = tmp_path
        config.build.ignored_folders = ["_private", "drafts"]
        config.advanced.quarto_enabled = False
        return config

    @pytest.fixture
    def handler(self, config):
        """Create a handler with a mock callback."""
        callback = Mock()
        return FoliateEventHandler(config, callback, debounce_seconds=0.05)

    # --- Event Filtering Tests ---

    def test_ignores_directory_events(self, handler):
        """Should ignore events on directories."""
        event = DirCreatedEvent("/path/to/vault/new_dir")

        handler.on_any_event(event)

        # No changes should be pending
        assert handler.pending_changes == []

    def test_ignores_git_directory(self, handler):
        """Should ignore events in .git directory."""
        event = FileModifiedEvent("/path/to/vault/.git/objects/abc123")

        handler.on_any_event(event)

        assert handler.pending_changes == []

    def test_ignores_build_directory(self, handler):
        """Should ignore events in .foliate/build directory."""
        event = FileModifiedEvent("/path/to/vault/.foliate/build/index.html")

        handler.on_any_event(event)

        assert handler.pending_changes == []

    def test_ignores_configured_folders(self, handler):
        """Should ignore events in folders listed in ignored_folders config."""
        # Test _private folder
        event = FileModifiedEvent("/path/to/vault/_private/secret.md")
        handler.on_any_event(event)
        assert handler.pending_changes == []

        # Test drafts folder
        event = FileModifiedEvent("/path/to/vault/drafts/wip.md")
        handler.on_any_event(event)
        assert handler.pending_changes == []

    def test_ignores_irrelevant_extensions(self, handler):
        """Should ignore files with irrelevant extensions."""
        # Note: .txt is a supported asset extension, so it's NOT ignored
        irrelevant_files = [
            "/vault/file.py",
            "/vault/file.js",
            "/vault/file.json",
            "/vault/file.exe",
            "/vault/file.rb",
            "/vault/file",  # no extension
        ]

        for path in irrelevant_files:
            handler.pending_changes.clear()
            event = FileModifiedEvent(path)
            handler.on_any_event(event)
            assert handler.pending_changes == [], f"Should ignore {path}"

    def test_tracks_markdown_files(self, handler):
        """Should track changes to markdown files."""
        event = FileModifiedEvent("/vault/notes/page.md")

        handler.on_any_event(event)

        # Give the thread time to start (but we'll check pending_changes)
        assert "/vault/notes/page.md" in handler.pending_changes

    def test_tracks_qmd_files(self, handler):
        """Should track changes to Quarto files."""
        event = FileModifiedEvent("/vault/research/paper.qmd")

        handler.on_any_event(event)

        assert "/vault/research/paper.qmd" in handler.pending_changes

    def test_tracks_html_files(self, handler):
        """Should track changes to HTML template files."""
        event = FileModifiedEvent("/vault/.foliate/templates/layout.html")

        handler.on_any_event(event)

        assert "/vault/.foliate/templates/layout.html" in handler.pending_changes

    def test_tracks_css_files(self, handler):
        """Should track changes to CSS files."""
        event = FileModifiedEvent("/vault/.foliate/static/style.css")

        handler.on_any_event(event)

        assert "/vault/.foliate/static/style.css" in handler.pending_changes

    def test_tracks_toml_files(self, handler):
        """Should track changes to config files."""
        event = FileModifiedEvent("/vault/.foliate/config.toml")

        handler.on_any_event(event)

        assert "/vault/.foliate/config.toml" in handler.pending_changes

    def test_tracks_asset_files(self, handler):
        """Should track changes to asset files (images, etc.)."""
        asset_files = [
            "/vault/assets/image.png",
            "/vault/assets/photo.jpg",
            "/vault/assets/icon.svg",
            "/vault/assets/doc.pdf",
        ]

        for path in asset_files:
            handler.pending_changes.clear()
            event = FileModifiedEvent(path)
            handler.on_any_event(event)
            assert path in handler.pending_changes, f"Should track {path}"

    def test_does_not_duplicate_pending_changes(self, handler):
        """Should not add duplicate paths to pending_changes."""
        path = "/vault/notes/page.md"
        event = FileModifiedEvent(path)

        # Trigger event twice
        handler.on_any_event(event)
        handler.on_any_event(event)

        # Should only appear once
        assert handler.pending_changes.count(path) == 1

    # --- Change Categorization Tests ---

    def test_html_triggers_full_rebuild(self, handler):
        """HTML changes should trigger a full rebuild."""
        handler.pending_changes = ["/vault/.foliate/templates/layout.html"]

        handler.process_changes()

        handler.rebuild_callback.assert_called_once_with(force=True)

    def test_css_triggers_full_rebuild(self, handler):
        """CSS changes should trigger a full rebuild."""
        handler.pending_changes = ["/vault/.foliate/static/style.css"]

        handler.process_changes()

        handler.rebuild_callback.assert_called_once_with(force=True)

    def test_toml_triggers_full_rebuild(self, handler):
        """Config changes should trigger a full rebuild."""
        handler.pending_changes = ["/vault/.foliate/config.toml"]

        handler.process_changes()

        handler.rebuild_callback.assert_called_once_with(force=True)

    def test_markdown_triggers_incremental_rebuild(self, handler):
        """Markdown changes should trigger an incremental rebuild."""
        handler.pending_changes = ["/vault/notes/page.md"]

        handler.process_changes()

        handler.rebuild_callback.assert_called_once_with(force=False)

    def test_mixed_changes_triggers_full_rebuild(self, handler):
        """Mixed changes including templates should trigger full rebuild."""
        handler.pending_changes = [
            "/vault/notes/page.md",
            "/vault/.foliate/static/style.css",
            "/vault/other/file.md",
        ]

        handler.process_changes()

        handler.rebuild_callback.assert_called_once_with(force=True)

    def test_empty_pending_changes_no_rebuild(self, handler):
        """Empty pending changes should not trigger rebuild."""
        handler.pending_changes = []

        handler.process_changes()

        handler.rebuild_callback.assert_not_called()

    def test_process_changes_clears_pending(self, handler):
        """Processing should clear pending changes list."""
        handler.pending_changes = ["/vault/notes/page.md", "/vault/other/file.md"]

        handler.process_changes()

        assert handler.pending_changes == []

    # --- Quarto Processing Tests ---

    def test_qmd_triggers_preprocessing_when_enabled(self, handler, tmp_path):
        """QMD files should be preprocessed when quarto is enabled."""
        handler.config.advanced.quarto_enabled = True
        qmd_path = tmp_path / "paper.qmd"
        qmd_path.touch()
        handler.pending_changes = [str(qmd_path)]

        with patch("foliate.quarto.preprocess_quarto") as mock_preprocess:
            handler.process_changes()

            mock_preprocess.assert_called_once()
            call_args = mock_preprocess.call_args
            assert call_args[0][0] == handler.config
            assert call_args[1]["single_file"] == qmd_path

    def test_qmd_no_preprocessing_when_disabled(self, handler, tmp_path):
        """QMD files should not be preprocessed when quarto is disabled."""
        handler.config.advanced.quarto_enabled = False
        qmd_path = tmp_path / "paper.qmd"
        handler.pending_changes = [str(qmd_path)]

        with patch("foliate.quarto.preprocess_quarto") as mock_preprocess:
            handler.process_changes()

            mock_preprocess.assert_not_called()

    # --- Debounce Behavior Tests ---

    def test_debounce_prevents_rapid_rebuilds(self, config):
        """Multiple rapid events should be debounced into one rebuild."""
        callback = Mock()
        handler = FoliateEventHandler(config, callback, debounce_seconds=0.1)

        # Trigger multiple events rapidly
        for i in range(5):
            event = FileModifiedEvent(f"/vault/notes/page{i}.md")
            handler.on_any_event(event)

        # Wait for debounce period plus processing
        time.sleep(0.2)

        # Should have only rebuilt once (or possibly twice due to timing)
        assert callback.call_count <= 2

    def test_debounce_batches_multiple_files(self, config):
        """Multiple file changes within debounce window should be batched."""
        callback = Mock()
        handler = FoliateEventHandler(config, callback, debounce_seconds=0.1)

        # Add multiple changes
        handler.pending_changes = [
            "/vault/notes/page1.md",
            "/vault/notes/page2.md",
            "/vault/notes/page3.md",
        ]

        handler.process_changes()

        # Single rebuild call for all files
        callback.assert_called_once()

    def test_updates_last_rebuild_time(self, handler):
        """Processing changes should update last_rebuild_time."""
        handler.pending_changes = ["/vault/notes/page.md"]
        initial_time = handler.last_rebuild_time

        handler.process_changes()

        assert handler.last_rebuild_time > initial_time

    # --- Thread Safety Tests ---

    def test_concurrent_events_thread_safe(self, config):
        """Concurrent events should be handled without race conditions."""
        callback = Mock()
        # Longer debounce to collect all events
        handler = FoliateEventHandler(config, callback, debounce_seconds=0.2)

        def trigger_events(start_idx):
            for i in range(10):
                event = FileModifiedEvent(f"/vault/notes/page{start_idx}_{i}.md")
                handler.on_any_event(event)

        # Start multiple threads triggering events
        threads = []
        for i in range(3):
            t = threading.Thread(target=trigger_events, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to finish triggering
        for t in threads:
            t.join()

        # Wait for debounce and processing
        time.sleep(0.4)

        # Should have rebuilt at least once
        assert callback.call_count >= 1

        # All pending changes should be cleared after processing
        # (may need a short sleep for the last process to complete)
        time.sleep(0.1)
        assert handler.pending_changes == []

    def test_lock_prevents_concurrent_list_modification(self, config):
        """The rebuild_lock should prevent race conditions on pending_changes."""
        callback = Mock()
        handler = FoliateEventHandler(config, callback, debounce_seconds=1.0)

        # Manually test lock behavior
        with handler.rebuild_lock:
            # While holding lock, add change
            handler.pending_changes.append("/vault/notes/test.md")
            # Another thread trying to access should block
            # (we can't easily test blocking, but we verify no exception)
            assert len(handler.pending_changes) == 1

        assert len(handler.pending_changes) == 1


class TestWatchFunction:
    """Tests for the watch() function."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a config for testing watch function."""
        config = Config()
        config.vault_path = tmp_path
        config.config_path = tmp_path / ".foliate" / "config.toml"

        # Create necessary directories
        (tmp_path / ".foliate").mkdir()
        (tmp_path / ".foliate" / "config.toml").write_text("[site]\nname = 'Test'")

        return config

    def test_watch_no_vault_path_returns_early(self, config):
        """Watch should return early if no vault_path configured."""
        config.vault_path = None

        with patch("foliate.watch.do_build") as mock_build:
            watch(config)

            mock_build.assert_not_called()

    def test_watch_performs_initial_build(self, config):
        """Watch should perform initial build on startup."""
        with (
            patch("foliate.watch.do_build") as mock_build,
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()

            # Make the observer.start() raise to exit the loop
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config)
            except KeyboardInterrupt:
                pass

            mock_build.assert_called_once_with(config=config, force_rebuild=False)

    def test_watch_starts_dev_server(self, config):
        """Watch should start a development server."""
        with (
            patch("foliate.watch.do_build"),
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config, port=9000)
            except KeyboardInterrupt:
                pass

            mock_server.assert_called_once()
            call_args = mock_server.call_args
            assert call_args[0][1] == 9000  # port
            assert call_args[1]["background"] is True

    def test_watch_schedules_vault_directory(self, config):
        """Watch should schedule the vault directory for observation."""
        with (
            patch("foliate.watch.do_build"),
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config)
            except KeyboardInterrupt:
                pass

            # Should have scheduled at least the vault directory
            mock_observer.schedule.assert_called()
            scheduled_paths = [
                call[0][1] for call in mock_observer.schedule.call_args_list
            ]
            assert str(config.vault_path) in scheduled_paths

    def test_watch_schedules_templates_if_exists(self, config):
        """Watch should also observe .foliate/templates if it exists."""
        templates_dir = config.vault_path / ".foliate" / "templates"
        templates_dir.mkdir()

        with (
            patch("foliate.watch.do_build"),
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config)
            except KeyboardInterrupt:
                pass

            scheduled_paths = [
                call[0][1] for call in mock_observer.schedule.call_args_list
            ]
            assert str(templates_dir) in scheduled_paths

    def test_watch_schedules_static_if_exists(self, config):
        """Watch should also observe .foliate/static if it exists."""
        static_dir = config.vault_path / ".foliate" / "static"
        static_dir.mkdir()

        with (
            patch("foliate.watch.do_build"),
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config)
            except KeyboardInterrupt:
                pass

            scheduled_paths = [
                call[0][1] for call in mock_observer.schedule.call_args_list
            ]
            assert str(static_dir) in scheduled_paths

    def test_watch_cleanup_on_keyboard_interrupt(self, config):
        """Watch should properly cleanup on KeyboardInterrupt."""
        with (
            patch("foliate.watch.do_build"),
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
            patch("foliate.watch.time.sleep") as mock_sleep,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_process = MagicMock()
            mock_server.return_value = mock_process

            # First sleep succeeds, second raises KeyboardInterrupt
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            watch(config)

            # Should stop observer and terminate server
            mock_observer.stop.assert_called_once()
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once()
            mock_observer.join.assert_called_once()

    def test_watch_handles_null_server_process(self, config):
        """Watch should handle case where server process is None."""
        with (
            patch("foliate.watch.do_build"),
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
            patch("foliate.watch.time.sleep") as mock_sleep,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = None  # Server didn't start

            mock_sleep.side_effect = KeyboardInterrupt()

            watch(config)

            # Should still stop observer without error
            mock_observer.stop.assert_called_once()


class TestRebuildCallback:
    """Tests for the rebuild callback created in watch()."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a config for testing."""
        config = Config()
        config.vault_path = tmp_path
        config.config_path = tmp_path / ".foliate" / "config.toml"
        (tmp_path / ".foliate").mkdir()
        (tmp_path / ".foliate" / "config.toml").write_text("[site]\nname = 'Test'")
        return config

    def test_rebuild_callback_force_false(self, config):
        """Rebuild callback with force=False should call build without force."""
        with (
            patch("foliate.watch.do_build") as mock_build,
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()

            # Capture the handler to get the callback
            handler_captured = None

            def capture_handler(handler, *_args, **_kwargs):
                nonlocal handler_captured
                handler_captured = handler

            mock_observer.schedule.side_effect = capture_handler
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config)
            except KeyboardInterrupt:
                pass

            # Reset mock to clear initial build call
            mock_build.reset_mock()

            # Call the rebuild callback
            if handler_captured:
                handler_captured.rebuild_callback(force=False)
                mock_build.assert_called_with(config=config, force_rebuild=False)

    def test_rebuild_callback_force_true(self, config):
        """Rebuild callback with force=True should call build with force."""
        with (
            patch("foliate.watch.do_build") as mock_build,
            patch("foliate.resources.start_dev_server") as mock_server,
            patch("foliate.watch.Observer") as mock_observer_class,
        ):
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer
            mock_server.return_value = MagicMock()

            handler_captured = None

            def capture_handler(handler, *_args, **_kwargs):
                nonlocal handler_captured
                handler_captured = handler

            mock_observer.schedule.side_effect = capture_handler
            mock_observer.start.side_effect = KeyboardInterrupt()

            try:
                watch(config)
            except KeyboardInterrupt:
                pass

            mock_build.reset_mock()

            if handler_captured:
                handler_captured.rebuild_callback(force=True)
                mock_build.assert_called_with(config=config, force_rebuild=True)


class TestRelevantExtensions:
    """Tests for the relevant_extensions set in FoliateEventHandler."""

    def test_includes_markdown_extensions(self, tmp_path):
        """Should include .md extension."""
        config = Config()
        config.vault_path = tmp_path
        handler = FoliateEventHandler(config, Mock())

        assert ".md" in handler.relevant_extensions

    def test_includes_quarto_extensions(self, tmp_path):
        """Should include .qmd extension."""
        config = Config()
        config.vault_path = tmp_path
        handler = FoliateEventHandler(config, Mock())

        assert ".qmd" in handler.relevant_extensions

    def test_includes_template_extensions(self, tmp_path):
        """Should include .html extension."""
        config = Config()
        config.vault_path = tmp_path
        handler = FoliateEventHandler(config, Mock())

        assert ".html" in handler.relevant_extensions

    def test_includes_style_extensions(self, tmp_path):
        """Should include .css extension."""
        config = Config()
        config.vault_path = tmp_path
        handler = FoliateEventHandler(config, Mock())

        assert ".css" in handler.relevant_extensions

    def test_includes_config_extensions(self, tmp_path):
        """Should include .toml extension."""
        config = Config()
        config.vault_path = tmp_path
        handler = FoliateEventHandler(config, Mock())

        assert ".toml" in handler.relevant_extensions

    def test_includes_asset_extensions(self, tmp_path):
        """Should include common asset extensions."""
        config = Config()
        config.vault_path = tmp_path
        handler = FoliateEventHandler(config, Mock())

        # Check common asset types (lowercased)
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf"]:
            assert ext in handler.relevant_extensions, f"Missing {ext}"
