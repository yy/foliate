"""Logging utilities for foliate.

Provides a simple, centralized logging system that supports:
- Configurable verbosity via --verbose flag
- Separate handling for errors/warnings vs info/debug
- Clean output format suitable for CLI usage
"""

import logging
import sys

# Module-level logger
_logger: logging.Logger | None = None

# Log level names for external use
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR


class CleanFormatter(logging.Formatter):
    """Formatter that outputs clean messages without log level prefixes."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


class PrefixFormatter(logging.Formatter):
    """Formatter that prefixes messages with level name for warnings/errors."""

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno >= logging.WARNING:
            return f"{record.levelname.capitalize()}: {record.getMessage()}"
        return record.getMessage()


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the application.

    Args:
        verbose: If True, show debug-level messages. Otherwise, show info and above.

    Returns:
        The configured logger instance.
    """
    global _logger

    logger = logging.getLogger("foliate")

    # Clear any existing handlers
    logger.handlers.clear()

    # Set level based on verbosity
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Create handlers for stdout (info/debug) and stderr (warnings/errors)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda r: r.levelno < logging.WARNING)
    stdout_handler.setFormatter(CleanFormatter())

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(PrefixFormatter())

    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the foliate logger, initializing with defaults if needed.

    Returns:
        The foliate logger instance.
    """
    global _logger
    if _logger is None:
        _logger = setup_logging(verbose=False)
    return _logger


# Convenience functions that delegate to the logger


def debug(msg: str) -> None:
    """Log a debug message (only shown with --verbose)."""
    get_logger().debug(msg)


def info(msg: str) -> None:
    """Log an info message (always shown)."""
    get_logger().info(msg)


def warning(msg: str) -> None:
    """Log a warning message to stderr."""
    get_logger().warning(msg)


def error(msg: str) -> None:
    """Log an error message to stderr."""
    get_logger().error(msg)
