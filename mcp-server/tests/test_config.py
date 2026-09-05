"""Config loading (AD-7)."""

from __future__ import annotations

import pytest

from mcp_notif.config import DEFAULT_TOKEN_DB_PATH, load_config


def test_defaults_when_env_empty():
    cfg = load_config({})
    assert cfg.fcm_service_account_path is None
    assert cfg.mcp_auth_token == ""
    assert cfg.enrollment_token == ""
    assert cfg.token_db_path == DEFAULT_TOKEN_DB_PATH


def test_reads_env_overrides():
    cfg = load_config(
        {
            "FCM_SERVICE_ACCOUNT_PATH": "/svc.json",
            "MCP_AUTH_TOKEN": "t1",
            "ENROLLMENT_TOKEN": "t2",
            "TOKEN_DB_PATH": "/data/x.db",
        }
    )
    assert cfg.fcm_service_account_path == "/svc.json"
    assert cfg.mcp_auth_token == "t1"
    assert cfg.enrollment_token == "t2"
    assert cfg.token_db_path == "/data/x.db"


def test_require_auth_tokens_raises_when_missing():
    cfg = load_config({"MCP_AUTH_TOKEN": "", "ENROLLMENT_TOKEN": ""})
    with pytest.raises(RuntimeError) as exc:
        cfg.require_auth_tokens()
    assert "MCP_AUTH_TOKEN" in str(exc.value)
    assert "ENROLLMENT_TOKEN" in str(exc.value)


def test_require_auth_tokens_passes_when_set():
    cfg = load_config({"MCP_AUTH_TOKEN": "a", "ENROLLMENT_TOKEN": "b"})
    cfg.require_auth_tokens()  # no raise
