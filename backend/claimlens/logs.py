"""Logging: plain text locally, one JSON object per line on Cloud Run (indexed as jsonPayload)."""

import json
import logging
import traceback

FIELDS = ("user", "method", "path", "status", "latency_ms", "case_id")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"severity": record.levelname, "message": record.getMessage(), "logger": record.name}
        out.update({k: getattr(record, k) for k in FIELDS if hasattr(record, k)})
        if record.exc_info and record.exc_info[0]:
            # where it failed and what kind of error, but not its message: parse errors can quote patient data
            kind, _, tb = record.exc_info
            out["exception"] = "".join(traceback.format_tb(tb)) + kind.__name__
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
    # uvicorn keeps its own plain-text handlers: send its errors through ours, and drop its access lines
    # (the request middleware already logs every /api call, with the user)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def case_logger(case_id: str, user: str | None) -> logging.LoggerAdapter:
    """Pipeline logger whose lines carry the case and its owner."""
    return logging.LoggerAdapter(logging.getLogger("claimlens.pipeline"), {"case_id": case_id, "user": user})
