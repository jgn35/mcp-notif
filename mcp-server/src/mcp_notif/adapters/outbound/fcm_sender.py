"""FCM sender adapter (AD-2).

Sends a **data-only** FCM message via firebase-admin and translates firebase
exceptions into the enumerated ErrorType set. The firebase-specific mapping
lives here so the application core never imports firebase-admin.

A `FcmError` carries a fully-formed `NotifyError`; the core surfaces it to the
LLM verbatim. Tests inject a `FakeFcmSender` (see tests/) so no live Google
credentials are ever needed.
"""

from __future__ import annotations

import asyncio
import threading

from ...errors import ErrorType, NotifyError
from ...ports import FcmError

# firebase-admin is imported lazily inside the adapter so the module imports
# cleanly in environments (and tests) that never construct the real sender.


def _map_firebase_error(exc: Exception) -> NotifyError:
    """Map a firebase_admin.exceptions.FirebaseError to a NotifyError."""
    from firebase_admin import exceptions as fbe
    from firebase_admin import messaging as fbm

    msg = str(exc) or exc.__class__.__name__

    # Order matters: most-specific subclasses first.
    if isinstance(exc, fbm.UnregisteredError) or isinstance(exc, fbe.NotFoundError):
        return NotifyError(
            ErrorType.FCM_UNREGISTERED,
            "Device token is no longer valid. The device must re-enroll via POST /enroll.",
        )
    if isinstance(exc, fbe.InvalidArgumentError):
        return NotifyError(ErrorType.FCM_INVALID_ARGUMENT, f"FCM rejected the payload: {msg}")
    if isinstance(
        exc,
        (
            fbm.SenderIdMismatchError,
            fbm.ThirdPartyAuthError,
            fbe.PermissionDeniedError,
            fbe.UnauthenticatedError,
        ),
    ):
        return NotifyError(
            ErrorType.FCM_PERMISSION_DENIED,
            "FCM service account is not authorized for this project.",
        )
    if isinstance(exc, fbm.QuotaExceededError) or isinstance(exc, fbe.ResourceExhaustedError):
        return NotifyError(ErrorType.FCM_THROTTLED, "FCM rate limit exceeded.")
    if isinstance(
        exc,
        (fbe.InternalError, fbe.UnavailableError, fbe.DeadlineExceededError, fbe.UnknownError),
    ):
        return NotifyError(ErrorType.FCM_INTERNAL, f"FCM internal error: {msg}")
    # Any other FirebaseError is treated as a retryable internal/server fault.
    return NotifyError(ErrorType.FCM_INTERNAL, f"FCM error: {msg}")


def _map_transport_error(exc: Exception) -> NotifyError:
    return NotifyError(ErrorType.NETWORK_ERROR, f"Network error reaching FCM: {exc}")


class FirebaseFcmSender:
    """Default FcmSender backed by firebase-admin (service account OAuth2)."""

    def __init__(self, service_account_path: str | None) -> None:
        self._service_account_path = service_account_path
        self._app = None
        self._lock = threading.Lock()

    def _ensure_app(self):
        if self._app is not None:
            return
        with self._lock:
            if self._app is not None:
                return
            from firebase_admin import credentials, initialize_app

            if not self._service_account_path:
                raise FcmError(
                    NotifyError(
                        ErrorType.FCM_PERMISSION_DENIED,
                        "FCM_SERVICE_ACCOUNT_PATH is not configured.",
                    )
                )
            try:
                cred = credentials.Certificate(self._service_account_path)
                self._app = initialize_app(cred, name="mcp-notif-fcm")
            except FcmError:
                raise
            except Exception as exc:
                raise FcmError(
                    NotifyError(
                        ErrorType.FCM_PERMISSION_DENIED,
                        f"Invalid FCM service account: {exc}",
                    )
                ) from exc

    async def send(self, device_token: str, data: dict[str, str]) -> str:
        return await asyncio.to_thread(self._send_sync, device_token, data)

    def _send_sync(self, device_token: str, data: dict[str, str]) -> str:
        from firebase_admin import exceptions as fbe
        from firebase_admin import messaging

        try:
            self._ensure_app()
            # data-only message: no `notification` field is set.
            # `token` accepts the FCM registration token that the Android app
            # obtains via FirebaseMessaging.getInstance().token.  firebase-admin
            # 7.5 deprecates `token` in favor of `fid` (Firebase Installation ID),
            # but `fid` expects a different identifier — using it with an FCM
            # registration token causes fcm_unregistered.  `token` still works
            # during the migration period.
            message = messaging.Message(data=data, token=device_token)
            return messaging.send(message, app=self._app)
        except FcmError:
            raise
        except fbe.FirebaseError as exc:
            raise FcmError(_map_firebase_error(exc)) from exc
        except Exception as exc:
            # Any non-Firebase failure during send is a transport/network fault
            # (matrix: FCM unreachable -> network_error), never FCM_INTERNAL.
            # Note: requests.exceptions.RequestException subclasses IOError/OSError,
            # so it is covered here without a separate branch.
            raise FcmError(_map_transport_error(exc)) from exc
