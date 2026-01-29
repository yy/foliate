"""Tests for foliate logging module."""

import logging

import pytest

from foliate import logging as foliate_logging


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the logger state between tests."""
    foliate_logging._logger = None
    # Also reset the actual logger if it exists
    logger = logging.getLogger("foliate")
    logger.handlers.clear()
    yield
    foliate_logging._logger = None


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_returns_logger(self):
        """setup_logging should return a Logger instance."""
        logger = foliate_logging.setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "foliate"

    def test_verbose_sets_debug_level(self):
        """verbose=True should set logger to DEBUG level."""
        logger = foliate_logging.setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_non_verbose_sets_info_level(self):
        """verbose=False should set logger to INFO level."""
        logger = foliate_logging.setup_logging(verbose=False)
        assert logger.level == logging.INFO

    def test_creates_two_handlers(self):
        """Should create separate handlers for stdout and stderr."""
        logger = foliate_logging.setup_logging()
        assert len(logger.handlers) == 2

    def test_clears_existing_handlers(self):
        """Should clear existing handlers on repeated calls."""
        logger = foliate_logging.setup_logging()
        assert len(logger.handlers) == 2
        logger = foliate_logging.setup_logging()  # Call again
        assert len(logger.handlers) == 2  # Should still be 2, not 4


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self):
        """get_logger should return a Logger instance."""
        logger = foliate_logging.get_logger()
        assert isinstance(logger, logging.Logger)

    def test_initializes_if_needed(self):
        """get_logger should initialize the logger if not already done."""
        assert foliate_logging._logger is None
        logger = foliate_logging.get_logger()
        assert foliate_logging._logger is logger

    def test_returns_same_logger(self):
        """get_logger should return the same logger on repeated calls."""
        logger1 = foliate_logging.get_logger()
        logger2 = foliate_logging.get_logger()
        assert logger1 is logger2


class TestLoggingOutput:
    """Tests for logging output formatting and routing."""

    def test_info_goes_to_stdout(self, capsys):
        """Info messages should go to stdout."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out
        assert captured.err == ""

    def test_warning_goes_to_stderr(self, capsys):
        """Warning messages should go to stderr."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.warning("test warning")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Warning: test warning" in captured.err

    def test_error_goes_to_stderr(self, capsys):
        """Error messages should go to stderr."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.error("test error")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Error: test error" in captured.err

    def test_debug_hidden_without_verbose(self, capsys):
        """Debug messages should not appear without verbose flag."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.debug("debug message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_debug_shown_with_verbose(self, capsys):
        """Debug messages should appear with verbose flag."""
        foliate_logging.setup_logging(verbose=True)
        foliate_logging.debug("debug message")
        captured = capsys.readouterr()
        assert "debug message" in captured.out

    def test_info_has_no_prefix(self, capsys):
        """Info messages should not have a level prefix."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.info("plain message")
        captured = capsys.readouterr()
        assert captured.out.strip() == "plain message"

    def test_warning_has_prefix(self, capsys):
        """Warning messages should have 'Warning:' prefix."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.warning("something")
        captured = capsys.readouterr()
        assert captured.err.strip() == "Warning: something"

    def test_error_has_prefix(self, capsys):
        """Error messages should have 'Error:' prefix."""
        foliate_logging.setup_logging(verbose=False)
        foliate_logging.error("something")
        captured = capsys.readouterr()
        assert captured.err.strip() == "Error: something"


class TestConvenienceFunctions:
    """Tests for the convenience logging functions."""

    def test_debug_function(self, capsys):
        """debug() should log at DEBUG level."""
        foliate_logging.setup_logging(verbose=True)
        foliate_logging.debug("debug test")
        captured = capsys.readouterr()
        assert "debug test" in captured.out

    def test_info_function(self, capsys):
        """info() should log at INFO level."""
        foliate_logging.setup_logging()
        foliate_logging.info("info test")
        captured = capsys.readouterr()
        assert "info test" in captured.out

    def test_warning_function(self, capsys):
        """warning() should log at WARNING level."""
        foliate_logging.setup_logging()
        foliate_logging.warning("warning test")
        captured = capsys.readouterr()
        assert "warning test" in captured.err

    def test_error_function(self, capsys):
        """error() should log at ERROR level."""
        foliate_logging.setup_logging()
        foliate_logging.error("error test")
        captured = capsys.readouterr()
        assert "error test" in captured.err


class TestLevelConstants:
    """Tests for module-level constants."""

    def test_debug_constant(self):
        """DEBUG constant should match logging.DEBUG."""
        assert foliate_logging.DEBUG == logging.DEBUG

    def test_info_constant(self):
        """INFO constant should match logging.INFO."""
        assert foliate_logging.INFO == logging.INFO

    def test_warning_constant(self):
        """WARNING constant should match logging.WARNING."""
        assert foliate_logging.WARNING == logging.WARNING

    def test_error_constant(self):
        """ERROR constant should match logging.ERROR."""
        assert foliate_logging.ERROR == logging.ERROR
