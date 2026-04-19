# AGENTS.md

Instructions for AI coding assistants (Codex, etc.) working on foliate.

## Cross-platform CI — read this before touching tests or filesystem/time code

CI runs on Linux, macOS, **and Windows**. Local runs on macOS/Linux will not catch Windows-only failures, and Windows failures have broken CI repeatedly. Before committing code that touches the filesystem, time, processes, or signals, think about Windows explicitly.

Common Windows gotchas:

- **POSIX-only APIs don't exist on Windows**: `time.tzset()`, `os.fork`, `os.geteuid`, `signal.SIGHUP/SIGUSR*`, `fcntl`, `resource`, `pwd`, `grp`. Guard with `@pytest.mark.skipif(not hasattr(time, "tzset"), reason="POSIX-only")` or `@pytest.mark.skipif(sys.platform == "win32", ...)`.
- **TZ env var has no effect** on Windows time functions. Any test that sets `TZ` to exercise timezone behavior needs a skip marker — it won't work on Windows regardless.
- **Path separators**: Use `pathlib.Path`, never hardcoded `/`. When asserting on paths in tests, normalize both sides (`.as_posix()` or compare `Path` objects, not strings).
- **Line endings and encoding**: Always pass `encoding="utf-8"` to `open()` / `Path.read_text()` / `Path.write_text()`. Don't assume `\n` — Windows writes `\r\n` by default in text mode.
- **File locking**: Windows locks open files. Close handles before deleting/renaming. `tempfile.NamedTemporaryFile(delete=False)` is usually safer than the default on Windows.
- **Case-insensitive filesystem**: Windows (and default macOS) treat `Foo.md` and `foo.md` as the same file. Don't rely on case to distinguish paths.

When adding a test that manipulates timezone, processes, signals, or low-level OS state, the default assumption should be "this probably needs a Windows skip." Check before committing.

## Before reporting work complete

- Run `uv run pytest` and confirm it passes.
- If the change touches filesystem/time/process/signal code, mentally walk through what happens on Windows — or just add a `skipif` guard if the test is inherently POSIX-specific.
- Do not commit code whose tests you have not run.
