"""Environment configuration.

Loads the four environment variables defined in the Solution Design:

  FCM_SERVICE_ACCOUNT_PATH  Path to Firebase service account JSON.
  MCP_AUTH_TOKEN             Bearer token guarding the MCP `notify` transport.
  ENROLLMENT_TOKEN           Bearer token guarding `POST /enroll`.
  TOKEN_DB_PATH              SQLite token store path (default /data/device_token.db).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_TOKEN_DB_PATH = "/data/device_token.db"


@dataclass(frozen=True)
class Config:
    fcm_service_account_path: str | None
    mcp_auth_token: str
    enrollment_token: str
    token_db_path: str

    def require_auth_tokens(self) -> None:
        """Raise if either auth token is empty — the app refuses to start without them."""
        missing = [
            name
            for name, value in (
                ("MCP_AUTH_TOKEN", self.mcp_auth_token),
                ("ENROLLMENT_TOKEN", self.enrollment_token),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required env var(s): {', '.join(missing)}")


def load_config(env: dict[str, str] | None = None) -> Config:
    src = env if env is not None else os.environ
    return Config(
        fcm_service_account_path=src.get("FCM_SERVICE_ACCOUNT_PATH") or None,
        mcp_auth_token=src.get("MCP_AUTH_TOKEN", ""),
        enrollment_token=src.get("ENROLLMENT_TOKEN", ""),
        token_db_path=src.get("TOKEN_DB_PATH") or DEFAULT_TOKEN_DB_PATH,
    )
