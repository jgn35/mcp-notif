"""Hexagonal ports (Protocols) and the exceptions the adapters raise.

The application core depends only on these Protocols, so the FCM sender and the
SQLite token store can be swapped for fakes in tests without touching core logic.
"""

from __future__ import annotations

from typing import Protocol

from .errors import NotifyError


class NoDeviceEnrolledError(Exception):
    """No device token in the store — the user must enroll a device."""


class StoreUnavailableError(Exception):
    """The SQLite store is corrupt, locked, or otherwise unusable."""


class FcmError(Exception):
    """Raised by an FcmSender adapter; carries the mapped NotifyError for the core."""

    def __init__(self, notify_error: NotifyError) -> None:
        super().__init__(notify_error.message)
        self.notify_error = notify_error


class TokenStore(Protocol):
    async def init(self) -> None: ...
    async def read(self) -> str: ...
    async def write(self, token: str) -> None: ...


class FcmSender(Protocol):
    async def send(self, device_token: str, data: dict[str, str]) -> str:
        """Send a data-only FCM message. Returns the FCM message id.

        Raises an exception on failure; the core maps it to an ErrorType.
        """
        ...
