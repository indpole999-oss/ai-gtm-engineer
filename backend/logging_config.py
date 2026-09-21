"""Structured application logging with correlation IDs and secret redaction."""

from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from backend.config import settings


request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|password|passwd|secret|token|api[_-]?key|credentials)",
    re.IGNORECASE,
)
BEARER_VALUE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
ASSIGNMENT_VALUE = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|credentials)(\s*[=:]\s*)([^\s,;]+)"
)
URL_CREDENTIALS = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?P<userinfo>[^/@\s]+)@")


def redact(value: Any) -> Any:
    """Recursively redact secret-bearing fields before serialization."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = URL_CREDENTIALS.sub(r"\g<scheme>[REDACTED]@", value)
        value = BEARER_VALUE.sub("Bearer [REDACTED]", value)
        return ASSIGNMENT_VALUE.sub(r"\1\2[REDACTED]", value)
    return value


class JsonFormatter(logging.Formatter):
    """Emit one safe JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key in ("method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = redact(getattr(record, key))
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, separators=(",", ":"))


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", request_id_context.get())
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
