"""
Module Name: app/utils/logger.py
Purpose   : Logging utilities for the application.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""
import sys
import os
import structlog
from typing import Optional, Dict, Any
import logging
from pathlib import Path

# Load environment variables directly in the logger module
try:
    from dotenv import load_dotenv
    # Try to find .env file in standard locations
    env_paths = [
        os.path.join(os.getcwd(), '.env'),  # Current directory
        os.path.join(Path(__file__).resolve().parent.parent.parent, '.env'),  # Project root
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            print(f"Loading environment from: {env_path}")
            load_dotenv(env_path)
            break
    else:
        print("No .env file found in standard locations")
except ImportError:
    print("python-dotenv not installed, environment variables must be set manually")

_loggers = {}

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
        try:
            # Make sure to resolve relative paths
            from pathlib import Path
            if not Path(log_file).is_absolute():
                # Resolve relative to project root
                base_dir = Path(__file__).resolve().parent.parent.parent
                log_file = str(base_dir / log_file)
                print(f"Resolved relative path to: {log_file}")

            # Ensure directory exists
            log_dir = Path(log_file).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            print(f"Log directory created/verified: {log_dir}")

            # Create file handler
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            logging.getLogger().addHandler(file_handler)

            # Log and print confirmation
            logger.info(f"File logging activated: {log_file}")
            print(f"File logging activated: {log_file}")
        except Exception as e:
            # Print error to make sure we see it
            print(f"ERROR setting up file logging: {str(e)}")
            import traceback
            print(traceback.format_exc())

    return logger

def get_logger(name: str = None, log_file: str = None, **logger_config) -> structlog.stdlib.BoundLogger:
    """ Get or create a logger with the given name and configuration

    Args:
        name: Logger name
        log_file: Direct path to log file (overrides environment variable)
        **logger_config: Additional logger configuration
    """
    global _loggers
    if name in _loggers:
        return _loggers[name]

    # Allow direct log_file specification to override environment
    if log_file is None:
        log_file = os.environ.get("SOLO_LOG_FILE")
    else:
        print(f"Using directly specified log file: {log_file}")

    # Add log_file to logger_config if specified
    if log_file:
        logger_config["log_file"] = log_file

    logger = setup_logger(**logger_config)

    _loggers[name] = logger
    return logger
