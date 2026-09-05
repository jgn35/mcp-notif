"""Inbound adapter 2: the plain-HTTP `POST /enroll` endpoint (AD-12).

The Android app does not speak MCP; enrollment is a simple REST call guarded by
a separate `ENROLLMENT_TOKEN`. The endpoint accepts only `{"device_token": ...}`
and overwrites the single-row token store (INSERT OR REPLACE — last enrollment
wins). It MUST NOT trigger a notification and MUST NOT accept any other fields.

Uses Starlette directly (FastMCP's http_app is already a Starlette app), so no
extra web-framework dependency is required.
"""

from __future__ import annotations

import hmac

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from ...ports import TokenStore

_EXPECTED_KEYS = frozenset({"device_token"})


def _check_bearer(authorization: str, expected_token: str) -> bool:
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):].strip()
    return bool(token) and hmac.compare_digest(token, expected_token)


async def _enroll(request: Request) -> Response:
    token_store: TokenStore = request.app.state.token_store
    enrollment_token: str = request.app.state.enrollment_token

    if not _check_bearer(request.headers.get("authorization", ""), enrollment_token):
        return Response(status_code=401)

    try:
        body = await request.json()
    except ValueError:
        return Response(status_code=400)

    if not isinstance(body, dict) or set(body.keys()) != _EXPECTED_KEYS:
        return Response(status_code=400)

    device_token = body["device_token"]
    if not isinstance(device_token, str) or device_token == "":
        return Response(status_code=400)

    await token_store.write(device_token)
    return JSONResponse({"status": "enrolled"})


def build_enroll_routes() -> list[Route]:
    return [Route("/enroll", _enroll, methods=["POST"])]
