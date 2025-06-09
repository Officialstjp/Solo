"""
Module Name: app/utils/logger.py
Purpose   : Logging utilities for the application.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""
import sys
import structlog
from typing import Optional, Dict, Any
import logging

def setup_logger(
        log_level: str = "INFO",
        json_format: bool = True,
        log_file: Optional[str] = None,
) -> structlog.stdlib.BoundLogger:
    """Configure and return a structured logger."""

    # set up standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure sturctlog processors
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()

    # add file handler if log_file is provided
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(file_handler)

    return logger
