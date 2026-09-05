"""firebase-admin exception -> ErrorType mapping (AD-8) and the FcmSender adapter.

The mapping function is tested directly with real firebase-admin exception
classes (installed as a dependency). The FirebaseFcmSender adapter is exercised
by monkeypatching firebase_admin.messaging.send so no network/credentials are
used, and by verifying the no-service-account configuration fails fast.
"""

from __future__ import annotations

import pytest

from mcp_notif.adapters.outbound.fcm_sender import FirebaseFcmSender, _map_firebase_error
from mcp_notif.errors import ErrorType
from mcp_notif.ports import FcmError

_PAYLOAD = {"title": "t", "short_message": "s", "detailed_message": "d"}


def _firebase(modpath, name):
    mod = pytest.importorskip(modpath)
    obj = getattr(mod, name)
    return obj


# (module, classname, args, expected ErrorType) for the mapping table.
MAPPING_CASES = [
    ("firebase_admin.exceptions", "InvalidArgumentError", "m", ErrorType.FCM_INVALID_ARGUMENT),
    ("firebase_admin.exceptions", "NotFoundError", "m", ErrorType.FCM_UNREGISTERED),
    ("firebase_admin.messaging", "UnregisteredError", "m", ErrorType.FCM_UNREGISTERED),
    ("firebase_admin.exceptions", "PermissionDeniedError", "m", ErrorType.FCM_PERMISSION_DENIED),
    ("firebase_admin.exceptions", "UnauthenticatedError", "m", ErrorType.FCM_PERMISSION_DENIED),
    ("firebase_admin.messaging", "SenderIdMismatchError", "m", ErrorType.FCM_PERMISSION_DENIED),
    ("firebase_admin.messaging", "ThirdPartyAuthError", "m", ErrorType.FCM_PERMISSION_DENIED),
    ("firebase_admin.messaging", "QuotaExceededError", "m", ErrorType.FCM_THROTTLED),
    ("firebase_admin.exceptions", "ResourceExhaustedError", "m", ErrorType.FCM_THROTTLED),
    ("firebase_admin.exceptions", "InternalError", "m", ErrorType.FCM_INTERNAL),
    ("firebase_admin.exceptions", "UnavailableError", "m", ErrorType.FCM_INTERNAL),
    ("firebase_admin.exceptions", "DeadlineExceededError", "m", ErrorType.FCM_INTERNAL),
    ("firebase_admin.exceptions", "UnknownError", "m", ErrorType.FCM_INTERNAL),
]


@pytest.mark.parametrize("modpath, clsname, arg, expected", MAPPING_CASES)
def test_map_firebase_error(modpath, clsname, arg, expected):
    cls = _firebase(modpath, clsname)
    err = cls(arg)
    mapped = _map_firebase_error(err)
    assert mapped.type is expected


async def test_adapter_no_service_account_fails_fast():
    sender = FirebaseFcmSender(service_account_path=None)
    with pytest.raises(FcmError) as exc:
        await sender.send("device-token", _PAYLOAD)
    assert exc.value.notify_error.type is ErrorType.FCM_PERMISSION_DENIED


async def test_adapter_maps_unregistered_error(monkeypatch):
    import firebase_admin.messaging as fbm

    sender = FirebaseFcmSender(service_account_path=None)
    # Skip real Firebase initialization.
    sender._app = object()  # not None, so _ensure_app is a no-op

    captured: list = []

    def boom(message, app=None):
        captured.append(message)
        raise fbm.UnregisteredError("token no longer valid", None)

    monkeypatch.setattr(fbm, "send", boom)

    with pytest.raises(FcmError) as exc:
        await sender.send("device-token", _PAYLOAD)
    assert exc.value.notify_error.type is ErrorType.FCM_UNREGISTERED
    # The real Message must target the device via fid (non-deprecated) and carry
    # exactly the data-only payload from the core.
    assert len(captured) == 1
    assert captured[0].fid == "device-token"
    assert captured[0].token is None
    assert captured[0].data == _PAYLOAD


async def test_adapter_maps_network_error(monkeypatch):
    import firebase_admin.messaging as fbm

    sender = FirebaseFcmSender(service_account_path=None)
    sender._app = object()

    def boom(message, app=None):
        raise ConnectionError("unreachable")

    monkeypatch.setattr(fbm, "send", boom)

    with pytest.raises(FcmError) as exc:
        await sender.send("device-token", _PAYLOAD)
    assert exc.value.notify_error.type is ErrorType.NETWORK_ERROR
    assert exc.value.notify_error.retryable is True
