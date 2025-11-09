from __future__ import annotations

import logging
import sys
from typing import Any, Callable, MutableMapping, cast

import structlog

from sync_hostaway.config import LOG_LEVEL

# Type alias for structlog processor
Processor = Callable[[Any, str, MutableMapping[str, Any]], Any]


def setup_logging() -> None:
    """
    Configures structured logging globally using structlog.

    In production (LOG_LEVEL=INFO): Outputs JSON for log aggregation
    In development (LOG_LEVEL=DEBUG): Outputs human-readable console format
    """
    # Configure standard library logging first
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s in %(name)s:%(lineno)d: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        level=LOG_LEVEL,
    )

    # Suppress noise from common libraries
    for noisy_logger in [
        "urllib3",
        "requests",
        "botocore",
        "boto3",
        "uvicorn.access",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Enable DEBUG logging for uvicorn.error to see details about invalid HTTP requests
    # The h11.RemoteProtocolError exception will show what's wrong with the request
    logging.getLogger("uvicorn.error").setLevel(logging.DEBUG)

    # Configure structlog
    # Choose renderer based on log level (JSON for production, Console for dev)
    renderer: Processor = cast(
        Processor,
        (
            structlog.processors.JSONRenderer()
            if LOG_LEVEL == "INFO"
            else structlog.dev.ConsoleRenderer(colors=True)
        ),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(LOG_LEVEL)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
