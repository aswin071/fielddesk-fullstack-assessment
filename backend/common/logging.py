import json
import logging
from datetime import UTC, datetime

from common.context import get_correlation_id

STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)
SENSITIVE_FIELDS = {"password", "token", "access", "refresh", "authorization", "cookie"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlationId": get_correlation_id(),
        }
        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = "[REDACTED]" if key.lower() in SENSITIVE_FIELDS else value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))

