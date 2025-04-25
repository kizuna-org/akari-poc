import logging
import sys

AkariLogger = logging.Logger


def getLogger(name: str, level: int = logging.DEBUG) -> AkariLogger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(logging.NullHandler())

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger
