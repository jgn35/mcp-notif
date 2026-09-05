"""Assembled Starlette app over HTTP: POST /enroll (AD-12) and MCP /mcp auth (AD-4).

Uses Starlette's TestClient so the lifespan (store init + MCP session manager)
actually runs. The fake FCM sender is injected; no network is used.
"""

from __future__ import annotations

import asyncio
import sqlite3

import pytest
from starlette.testclient import TestClient

from mcp_notif.adapters.outbound.token_store import SqliteTokenStore

from .conftest import make_app

ENROLL = "enroll-secret"


def _client(config, sender):
    app = make_app(config, sender)
    return TestClient(app)


def test_enroll_happy_persists_token(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post(
            "/enroll",
            headers={"Authorization": f"Bearer {ENROLL}"},
            json={"device_token": "device-xyz"},
        )
    assert r.status_code == 200
    assert r.json() == {"status": "enrolled"}
    # Token persisted in the single-row store.
    with sqlite3.connect(config.token_db_path) as conn:
        row = conn.execute("SELECT token FROM device_token WHERE id = 1").fetchone()
    assert row == ("device-xyz",)


def test_enroll_overwrites_previous(config, fake_sender):
    with _client(config, fake_sender) as client:
        client.post(
            "/enroll", headers={"Authorization": f"Bearer {ENROLL}"}, json={"device_token": "A"}
        )
        client.post(
            "/enroll", headers={"Authorization": f"Bearer {ENROLL}"}, json={"device_token": "B"}
        )
    store = SqliteTokenStore(config.token_db_path)
    assert asyncio.run(store.read()) == "B"


def test_enroll_no_auth_header_401(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post("/enroll", json={"device_token": "x"})
    assert r.status_code == 401


def test_enroll_wrong_token_401(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post(
            "/enroll",
            headers={"Authorization": "Bearer wrong"},
            json={"device_token": "x"},
        )
    assert r.status_code == 401


def test_enroll_missing_device_token_400(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post("/enroll", headers={"Authorization": f"Bearer {ENROLL}"}, json={})
    assert r.status_code == 400


def test_enroll_empty_device_token_400(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post(
            "/enroll",
            headers={"Authorization": f"Bearer {ENROLL}"},
            json={"device_token": ""},
        )
    assert r.status_code == 400


def test_enroll_extra_fields_400(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post(
            "/enroll",
            headers={"Authorization": f"Bearer {ENROLL}"},
            json={"device_token": "x", "extra": "y"},
        )
    assert r.status_code == 400


def test_enroll_non_string_device_token_400(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post(
            "/enroll",
            headers={"Authorization": f"Bearer {ENROLL}"},
            json={"device_token": 123},
        )
    assert r.status_code == 400


def test_enroll_non_json_body_400(config, fake_sender):
    with _client(config, fake_sender) as client:
        r = client.post(
            "/enroll",
            headers={"Authorization": f"Bearer {ENROLL}", "Content-Type": "application/json"},
            content=b"not json",
        )
    assert r.status_code == 400


def test_mcp_endpoint_requires_mcp_auth_token(config, fake_sender):
    """A request to the MCP transport without the MCP_AUTH_TOKEN is rejected (401)."""
    with _client(config, fake_sender) as client:
        r = client.post("/mcp/", headers={"Accept": "application/json, text/event-stream"})
    assert r.status_code == 401


def test_mcp_endpoint_accepts_correct_token(config, fake_sender):
    """With the correct bearer, the MCP transport does not 401."""
    with _client(config, fake_sender) as client:
        r = client.post(
            "/mcp/",
            headers={
                "Authorization": "Bearer mcp-secret",
                "Accept": "application/json, text/event-stream",
            },
        )
    assert r.status_code != 401


def test_app_refuses_to_start_without_auth_tokens(tmp_path, fake_sender):
    """Lifespan fails fast (RuntimeError) when MCP_AUTH_TOKEN/ENROLLMENT_TOKEN are empty."""
    from mcp_notif.app import create_app
    from mcp_notif.config import Config

    cfg = Config(
        fcm_service_account_path=None,
        mcp_auth_token="",
        enrollment_token="",
        token_db_path=str(tmp_path / "device_token.db"),
    )
    app = create_app(cfg, fcm_sender=fake_sender)
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass
