import logging
import sys

_AkariLogger = logging.Logger


def _getLogger(name: str, level: int = logging.DEBUG) -> _AkariLogger:
    """Sets up and provides a customized logger instance for use within the Akari framework.

    Creates a logger with the specified name and severity level. To prevent
    "No handlers could be found" warnings if the application using Akari doesn't
    configure logging, a `NullHandler` is added by default. Additionally, a
    `StreamHandler` is configured to output log messages to `sys.stdout`,
    using the same specified logging level.

    Args:
        name (str): The desired name for the logger (e.g., "Akari.Router").
        level (int): The minimum logging level the logger will handle (e.g.,
            `logging.DEBUG`, `logging.INFO`). Defaults to `logging.DEBUG`.

    Returns:
        _AkariLogger: The fully configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(logging.NullHandler())

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger
