"""Structured JSON logging (AD-10).

One JSON line per `notify` call to stdout. Podman captures stdout; no file
logging, no aggregation in V1.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime

from .core.notify import NotifyResult


def new_request_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_notify(result: NotifyResult, *, request_id: str, latency_ms: int) -> None:
    """Emit one structured JSON log line for a notify call."""
    line = {
        "request_id": request_id,
        "timestamp": now_iso(),
        "result": "success" if result.ok else "error",
        "latency_ms": latency_ms,
    }
    if result.ok:
        line["fcm_message_id"] = result.message_id
    elif result.error is not None:
        line["error_type"] = result.error.type.value
    sys.stdout.write(json.dumps(line) + "\n")
    sys.stdout.flush()
