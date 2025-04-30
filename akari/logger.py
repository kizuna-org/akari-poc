import logging
import sys

_AkariLogger = logging.Logger


def _getLogger(name: str, level: int = logging.DEBUG) -> _AkariLogger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(logging.NullHandler())

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger
