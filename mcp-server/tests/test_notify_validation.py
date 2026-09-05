"""notify validation + error mapping (AD-1, AD-8) — core.notify with fakes.

Validation must reject oversized/empty/non-string fields BEFORE reading the
token store or calling FCM (so the fake store is never touched on validation
errors, and the fake sender is never called).
"""

from __future__ import annotations

import pytest

from mcp_notif.core.notify import FIELD_LIMITS, notify
from mcp_notif.errors import ErrorType
from mcp_notif.ports import NoDeviceEnrolledError, StoreUnavailableError

from .conftest import FakeFcmSender, fcm_error


class RaisingStore:
    """A TokenStore that always raises NoDeviceEnrolled — proves validation runs first."""

    async def init(self) -> None: ...
    async def read(self) -> str:
        raise NoDeviceEnrolledError("should not reach here")
    async def write(self, token: str) -> None: ...


def _limit(name: str) -> int:
    return FIELD_LIMITS[name]


def _over(name: str) -> str:
    return "é" * (_limit(name) + 1)  # multibyte to test UTF-8 byte length


@pytest.mark.parametrize(
    "field, value",
    [
        ("title", _over("title")),
        ("short_message", _over("short_message")),
        ("detailed_message", _over("detailed_message")),
    ],
)
async def test_oversized_field_rejected_before_fcm(field, value):
    store = RaisingStore()
    sender = FakeFcmSender()
    result = await notify(
        **{"title": "t", "short_message": "s", "detailed_message": "d", field: value},
        token_store=store,
        fcm_sender=sender,
    )
    assert result.error is not None
    assert result.error.type is ErrorType.VALIDATION_ERROR
    assert sender.sent == []  # FCM never called


@pytest.mark.parametrize("field", ["title", "short_message", "detailed_message"])
async def test_empty_field_rejected(field):
    result = await notify(
        **{"title": "t", "short_message": "s", "detailed_message": "d", field: ""},
        token_store=RaisingStore(),
        fcm_sender=FakeFcmSender(),
    )
    assert result.error is not None
    assert result.error.type is ErrorType.VALIDATION_ERROR


async def test_non_string_field_rejected():
    result = await notify(
        title="t",
        short_message=123,  # type: ignore[arg-type]
        detailed_message="d",
        token_store=RaisingStore(),
        fcm_sender=FakeFcmSender(),
    )
    assert result.error is not None
    assert result.error.type is ErrorType.VALIDATION_ERROR


async def test_byte_limit_boundary_just_under():
    """A field at exactly the byte limit is accepted (boundary check)."""
    # Use a store with a token so we pass validation and reach FCM.
    class OkStore:
        async def init(self): ...
        async def read(self): return "dev-token"
        async def write(self, token): ...

    sender = FakeFcmSender()
    title = "a" * FIELD_LIMITS["title"]  # exactly 100 bytes
    result = await notify(
        title=title, short_message="s", detailed_message="d",
        token_store=OkStore(), fcm_sender=sender,
    )
    assert result.ok
    assert sender.sent[0][1]["title"] == title


async def test_no_device_enrolled_no_fcm_call():
    class EmptyStore:
        async def init(self): ...
        async def read(self):
            raise NoDeviceEnrolledError("none")
        async def write(self, token): ...

    sender = FakeFcmSender()
    result = await notify("t", "s", "d", token_store=EmptyStore(), fcm_sender=sender)
    assert result.error is not None
    assert result.error.type is ErrorType.NO_DEVICE_ENROLLED
    assert sender.sent == []


async def test_store_unavailable_maps_to_retryable_error():
    class CorruptStore:
        async def init(self): ...
        async def read(self):
            raise StoreUnavailableError("corrupt")
        async def write(self, token): ...

    sender = FakeFcmSender()
    result = await notify("t", "s", "d", token_store=CorruptStore(), fcm_sender=sender)
    assert result.error is not None
    assert result.error.type is ErrorType.STORE_UNAVAILABLE
    assert result.error.retryable is True
    assert sender.sent == []


async def test_fcm_unregistered_propagated():
    class OkStore:
        async def init(self): ...
        async def read(self): return "dev"
        async def write(self, token): ...

    sender = FakeFcmSender(raise_error=fcm_error(ErrorType.FCM_UNREGISTERED))
    result = await notify("t", "s", "d", token_store=OkStore(), fcm_sender=sender)
    assert result.error is not None
    assert result.error.type is ErrorType.FCM_UNREGISTERED
    assert result.error.retryable is False


async def test_fcm_throttled_is_retryable():
    class OkStore:
        async def init(self): ...
        async def read(self): return "dev"
        async def write(self, token): ...

    sender = FakeFcmSender(raise_error=fcm_error(ErrorType.FCM_THROTTLED))
    result = await notify("t", "s", "d", token_store=OkStore(), fcm_sender=sender)
    assert result.error is not None
    assert result.error.type is ErrorType.FCM_THROTTLED
    assert result.error.retryable is True
