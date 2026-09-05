"""notify tool end-to-end through the FastMCP server (call_tool) + data-only payload.

Exercises the full chain: MCP tool -> core -> token store -> FCM sender, with a
real SQLite store and a fake sender. Verifies the FCM data payload is data-only
(exactly the three keys, no `notification`) and that the success/error shapes
match the contract returned to the LLM.
"""

from __future__ import annotations

from mcp_notif.adapters.inbound.mcp_transport import build_mcp_server
from mcp_notif.adapters.outbound.token_store import SqliteTokenStore
from mcp_notif.config import Config
from mcp_notif.errors import ErrorType

from .conftest import FakeFcmSender, fcm_error


async def _setup(tmp_path, sender=None):
    cfg = Config(
        fcm_service_account_path=None,
        mcp_auth_token="mcp-secret",
        enrollment_token="enroll-secret",
        token_db_path=str(tmp_path / "device_token.db"),
    )
    store = SqliteTokenStore(cfg.token_db_path)
    await store.init()
    sender = sender if sender is not None else FakeFcmSender()
    mcp = build_mcp_server(store, sender, cfg.mcp_auth_token)
    return mcp, store, sender


async def _call(mcp, **args):
    return await mcp.call_tool("notify", args)


async def test_notify_success_returns_message_id(tmp_path):
    mcp, store, sender = await _setup(tmp_path)
    await store.write("device-token-1")
    res = await _call(mcp, title="Hi", short_message="short", detailed_message="details")
    assert res.is_error is False
    assert res.structured_content == {"message_id": "projects/x/messages/abc"}
    # Exactly one send, to the enrolled device token.
    assert len(sender.sent) == 1
    device, data = sender.sent[0]
    assert device == "device-token-1"
    # AD-2: data-only, exactly the three keys, nothing else.
    assert set(data.keys()) == {"title", "short_message", "detailed_message"}
    assert data == {"title": "Hi", "short_message": "short", "detailed_message": "details"}
    assert "notification" not in data


async def test_notify_oversized_returns_validation_error(tmp_path):
    mcp, store, sender = await _setup(tmp_path)
    await store.write("device-token-1")
    res = await _call(mcp, title="x" * 101, short_message="s", detailed_message="d")
    assert res.structured_content["error"]["type"] == "validation_error"
    assert sender.sent == []


async def test_notify_no_device_returns_no_device_enrolled(tmp_path):
    mcp, store, sender = await _setup(tmp_path)
    res = await _call(mcp, title="Hi", short_message="s", detailed_message="d")
    assert res.structured_content["error"]["type"] == "no_device_enrolled"
    assert sender.sent == []


async def test_notify_fcm_unregistered_returns_structured_error(tmp_path):
    sender = FakeFcmSender(raise_error=fcm_error(ErrorType.FCM_UNREGISTERED))
    mcp, store, _ = await _setup(tmp_path, sender)
    await store.write("device-token-1")
    res = await _call(mcp, title="Hi", short_message="s", detailed_message="d")
    # Returned as a structured payload, not raised — the LLM decides retry.
    assert res.structured_content["error"]["type"] == "fcm_unregistered"
    assert "message" in res.structured_content["error"]
