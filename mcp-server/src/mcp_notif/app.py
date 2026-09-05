"""Application entry point.

Assembles one ASGI app (Starlette) that mounts the MCP Streamable HTTP transport
at `/mcp` (AD-2) and adds the plain-HTTP `POST /enroll` route (AD-12). The SQLite
token store is initialized at startup, before either inbound adapter serves.
Run with: `uvicorn mcp_notif.app:app --host 127.0.0.1 --port 8080`.

Uses Starlette directly — FastMCP's `http_app()` already returns a Starlette
app — so no extra web framework (FastAPI) is required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount

from .adapters.inbound.enroll import build_enroll_routes
from .adapters.inbound.mcp_transport import build_mcp_server
from .adapters.outbound.fcm_sender import FirebaseFcmSender
from .adapters.outbound.token_store import SqliteTokenStore
from .config import Config, load_config
from .ports import FcmSender, TokenStore


def create_app(
    config: Config | None = None,
    *,
    token_store: TokenStore | None = None,
    fcm_sender: FcmSender | None = None,
) -> Starlette:
    cfg = config or load_config()
    store = token_store or SqliteTokenStore(cfg.token_db_path)
    sender = fcm_sender or FirebaseFcmSender(cfg.fcm_service_account_path)

    mcp = build_mcp_server(store, sender, cfg.mcp_auth_token)
    mcp_app = mcp.http_app(path="/")

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # Fail fast before serving if auth tokens are missing.
        cfg.require_auth_tokens()
        # AD-13: table created at startup, before either inbound adapter serves.
        await store.init()
        async with mcp_app.lifespan(app):
            yield

    routes = [Mount("/mcp", app=mcp_app), *build_enroll_routes()]
    app = Starlette(routes=routes, lifespan=lifespan)
    # The /enroll handler reads these from app state.
    app.state.token_store = store
    app.state.enrollment_token = cfg.enrollment_token
    return app


# Module-level app for `uvicorn mcp_notif.app:app`. Built from env at import;
# auth tokens are enforced at startup (lifespan), so import never fails.
app = create_app()
