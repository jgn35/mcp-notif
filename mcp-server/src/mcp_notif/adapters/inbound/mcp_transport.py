"""Inbound adapter 1: the MCP `notify` tool over Streamable HTTP (FastMCP 4.x).

Auth uses a StaticTokenVerifier (the configured `MCP_AUTH_TOKEN`). The tool
delegates to the application core and emits one structured log line per call.
On error it returns the structured `{"error": {...}}` payload (it does not raise)
so the LLM can read `error.type` and decide retry vs. skip.
"""

from __future__ import annotations

import time
from typing import Any

from fastmcp import FastMCP

from ...core.notify import notify as run_notify
from ...logging import log_notify, new_request_id
from ...ports import FcmSender, TokenStore


def build_mcp_server(
    token_store: TokenStore,
    fcm_sender: FcmSender,
    mcp_auth_token: str,
) -> FastMCP:
    auth = None
    if mcp_auth_token:
        from fastmcp.server.auth import StaticTokenVerifier

        auth = StaticTokenVerifier(tokens={mcp_auth_token: {"sub": "llm", "client_id": "llm"}})

    mcp = FastMCP("mcp-notif", auth=auth)

    @mcp.tool
    async def notify(title: str, short_message: str, detailed_message: str) -> dict[str, Any]:
        """Push a notification to the user's Android device via Firebase Cloud Messaging.

        Args:
            title: Short notification title (<= 100 UTF-8 bytes).
            short_message: Body shown in the system notification (<= 500 bytes).
            detailed_message: Full text shown when the notification is tapped (<= 3500 bytes).

        Returns:
            `{"message_id": "..."}` on success, or `{"error": {"type": ..., "message": ...}}`.
        """
        request_id = new_request_id()
        start = time.perf_counter()
        result = await run_notify(
            title,
            short_message,
            detailed_message,
            token_store=token_store,
            fcm_sender=fcm_sender,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_notify(result, request_id=request_id, latency_ms=latency_ms)
        if result.ok:
            return {"message_id": result.message_id}
        assert result.error is not None
        return result.error.to_dict()

    return mcp
