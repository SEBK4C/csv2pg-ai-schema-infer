"""Logging configuration for CSV2PG AI Schema Infer."""

import logging
import sys
from pathlib import Path
from typing import Any

from rich.logging import RichHandler


def setup_logger(
    name: str = "csv2pg",
    level: str = "INFO",
    log_file: Path | None = None,
) -> logging.Logger:
    """
    Set up logger with rich console handler and optional file handler.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Rich console handler
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=True,
    )
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s", datefmt="[%X]")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def log_structured(
    logger: logging.Logger,
    level: str,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log a structured message with additional context.

    Args:
        logger: Logger instance
        level: Log level (info, debug, warning, error, critical)
        message: Log message
        **kwargs: Additional context to log
    """
    log_func = getattr(logger, level.lower())
    context = " ".join(f"{k}={v}" for k, v in kwargs.items())
    log_func(f"{message} {context}")


# Default logger
logger = setup_logger()