"""Shared test fixtures and fakes.

Tests never touch the network or real Firebase: a FakeFcmSender records what
would be sent and can raise an FcmError to exercise the error paths.
"""

from __future__ import annotations

import pytest

from mcp_notif.adapters.outbound.token_store import SqliteTokenStore
from mcp_notif.config import Config
from mcp_notif.errors import ErrorType, NotifyError
from mcp_notif.ports import FcmError


class FakeFcmSender:
    """In-memory FcmSender. Records (device_token, data) per call.

    Set `raise_error` to an exception to simulate an FCM failure. To mimic the
    real adapter, raise an FcmError carrying a NotifyError.
    """

    def __init__(
        self,
        message_id: str = "projects/x/messages/abc",
        raise_error: Exception | None = None,
    ) -> None:
        self.message_id = message_id
        self.raise_error = raise_error
        self.sent: list[tuple[str, dict[str, str]]] = []

    async def send(self, device_token: str, data: dict[str, str]) -> str:
        self.sent.append((device_token, dict(data)))
        if self.raise_error is not None:
            raise self.raise_error
        return self.message_id


def fcm_error(error_type: ErrorType, message: str = "boom") -> FcmError:
    return FcmError(NotifyError(error_type, message))


def config_with(db_path: str) -> Config:
    return Config(
        fcm_service_account_path=None,
        mcp_auth_token="mcp-secret",
        enrollment_token="enroll-secret",
        token_db_path=db_path,
    )


@pytest.fixture
def store(tmp_path) -> SqliteTokenStore:
    return SqliteTokenStore(str(tmp_path / "device_token.db"))


@pytest.fixture
def config(tmp_path) -> Config:
    return config_with(str(tmp_path / "device_token.db"))


@pytest.fixture
def fake_sender() -> FakeFcmSender:
    return FakeFcmSender()


def make_app(config: Config, sender: FakeFcmSender):
    """Build the real Starlette app with a fake FCM sender and a real SQLite store."""
    from mcp_notif.app import create_app

    return create_app(
        config,
        token_store=SqliteTokenStore(config.token_db_path),
        fcm_sender=sender,
    )
