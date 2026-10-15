"""Logging: plain text locally, one JSON object per line on Cloud Run (indexed as jsonPayload)."""

import json
import logging

FIELDS = ("user", "method", "path", "status", "latency_ms", "case_id")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"severity": record.levelname, "message": record.getMessage(), "logger": record.name}
        out.update({k: getattr(record, k) for k in FIELDS if hasattr(record, k)})
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup(app_env: str) -> None:
    if app_env != "prod":
        logging.basicConfig(level=logging.INFO)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


def case_logger(case_id: str, user: str | None) -> logging.LoggerAdapter:
    """Pipeline logger whose lines carry the case and its owner."""
    return logging.LoggerAdapter(logging.getLogger("claimlens.pipeline"), {"case_id": case_id, "user": user})
