"""Logging related data will be written to this file."""
import sys
from pathlib import Path
from loguru import logger
Path("logs").mkdir(exist_ok=True)
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
"""Remove the default logger to avoid duplicate logs."""
logger.remove()
"""Configure the logger."""
logger.add(
    sys.stdout,
    level="DEBUG",
    format=LOG_FORMAT,
    colorize=True,
)
logger.add(
    "logs/forge.log",
    level="INFO",
    rotation="5 MB",
    retention="10 days",
    compression="zip",
    enqueue=True,
    format=LOG_FORMAT,
)
#Actually we can use the default python logger insted i am using Loguru package..... One stupid thing i did is first i initialized both and used nothing... later i realized..... Litrally it's my core ðŸ˜ðŸ˜…âœŒï¸
# Create a global logger instance to act as an interface between files (for importing and exporitng..... Litrally it is a ship.....)
__all__ = ["logger"]
