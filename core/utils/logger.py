"""
Logger Utility - Structured logging setup
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: str = "INFO",
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Setup structured logger
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level
        format_string: Custom format string
    
    Returns:
        Configured logger
    """
    # Configure the ROOT logger too, so that module-level loggers created with
    # logging.getLogger(__name__) elsewhere in the app (orchestrator, services,
    # generators) actually emit. Without this their records propagate to a root
    # with no handler and are silently dropped — which hides the entire
    # generation pipeline from the console.
    root = logging.getLogger()
    if not any(getattr(h, "_gamora_root", False) for h in root.handlers):
        root_handler = logging.StreamHandler(sys.stdout)
        root_handler.setLevel(getattr(logging, level.upper()))
        root_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root_handler._gamora_root = True
        root.addHandler(root_handler)
        root.setLevel(getattr(logging, level.upper()))
        # Third-party noise stays at WARNING
        for noisy in ("httpx", "httpcore", "hpack", "urllib3", "watchfiles"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Format
    if not format_string:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    # The root handler above already emits these records; without this
    # every line is printed twice.
    logger.propagate = False

    return logger
