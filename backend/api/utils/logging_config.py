"""CloudWatch logging configuration using watchtower."""

import logging
import os
import sys
from typing import Optional

import watchtower
from pythonjsonlogger import jsonlogger


_RESERVED_LOGRECORD_ATTRS = {
    "name", "msg", "args", "created", "filename", "funcName", "levelname",
    "levelno", "lineno", "module", "msecs", "message", "msg", "name",
    "pathname", "process", "processName", "relativeCreated", "thread",
    "threadName", "exc_info", "exc_text", "stack_info", "asctime"
}


def _sanitize_extra(extra: dict) -> dict:
    """Remove reserved LogRecord attributes from extra dict."""
    if not extra:
        return {}
    return {k: v for k, v in extra.items() if k not in _RESERVED_LOGRECORD_ATTRS}


def get_cloudwatch_handler(
    log_group: Optional[str] = None,
    stream_name: Optional[str] = None,
    region_name: Optional[str] = None,
) -> Optional[watchtower.CloudWatchLogHandler]:
    """Create CloudWatch log handler if AWS credentials are available."""
    log_group = log_group or os.getenv("CLOUDWATCH_LOG_GROUP", "broker-api-logs")
    stream_name = stream_name or os.getenv("CLOUDWATCH_LOG_STREAM", "broker-service")
    region_name = region_name or os.getenv("AWS_REGION", "us-east-1")

    if not os.getenv("AWS_ACCESS_KEY_ID") and not os.getenv("AWS_PROFILE"):
        return None

    try:
        handler = watchtower.CloudWatchLogHandler(
            log_group=log_group,
            stream_name=stream_name,
            boto3_client=__import__("boto3").client("logs", region_name=region_name),
        )
        formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            timestamp=True,
        )
        handler.setFormatter(formatter)
        return handler
    except Exception:
        return None


def setup_logging(
    log_level: str = "INFO",
    log_group: Optional[str] = None,
    stream_name: Optional[str] = None,
    region_name: Optional[str] = None,
) -> logging.Logger:
    """Configure application logging with CloudWatch support."""
    logger = logging.getLogger("broker")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = jsonlogger.JsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s",
        timestamp=True,
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    cw_handler = get_cloudwatch_handler(log_group, stream_name, region_name)
    if cw_handler:
        logger.addHandler(cw_handler)
        logger.info("CloudWatch logging enabled", extra=_sanitize_extra({"log_group": log_group, "stream_name": stream_name}))
    else:
        logger.info("CloudWatch logging not configured (no AWS credentials)")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(f"broker.{name}")