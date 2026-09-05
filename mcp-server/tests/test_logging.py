"""Structured JSON logging (AD-10)."""

from __future__ import annotations

import json

from mcp_notif.core.notify import NotifyResult
from mcp_notif.errors import ErrorType, NotifyError
from mcp_notif.logging import log_notify, new_request_id


def _capture(capsys):
    captured = capsys.readouterr()
    return [json.loads(line) for line in captured.out.strip().splitlines() if line]


def test_log_success_line(capsys):
    result = NotifyResult(message_id="projects/x/messages/1", error=None)
    log_notify(result, request_id="req-1", latency_ms=12)
    lines = _capture(capsys)
    assert len(lines) == 1
    line = lines[0]
    assert line["request_id"] == "req-1"
    assert line["result"] == "success"
    assert line["latency_ms"] == 12
    assert line["fcm_message_id"] == "projects/x/messages/1"
    assert "timestamp" in line
    assert "error_type" not in line


def test_log_error_line(capsys):
    result = NotifyResult(message_id=None, error=NotifyError(ErrorType.FCM_UNREGISTERED, "nope"))
    log_notify(result, request_id="req-2", latency_ms=5)
    lines = _capture(capsys)
    assert len(lines) == 1
    line = lines[0]
    assert line["result"] == "error"
    assert line["error_type"] == "fcm_unregistered"
    assert "fcm_message_id" not in line


def test_new_request_id_unique():
    assert new_request_id() != new_request_id()
