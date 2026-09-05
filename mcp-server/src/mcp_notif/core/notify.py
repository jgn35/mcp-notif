"""Application core: the `notify` tool logic (validation + FCM message build).

The core knows nothing of HTTP, the MCP protocol, or firebase-admin. It depends
only on the TokenStore and FcmSender ports. All errors are returned as
structured NotifyError results — the server never retries; the LLM decides.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ErrorType, NotifyError
from ..ports import FcmError, FcmSender, NoDeviceEnrolledError, StoreUnavailableError, TokenStore

# AD-1: field byte limits (UTF-8).
FIELD_LIMITS: dict[str, int] = {
    "title": 100,
    "short_message": 500,
    "detailed_message": 3500,
}


@dataclass(frozen=True)
class NotifyResult:
    message_id: str | None
    error: NotifyError | None

    @property
    def ok(self) -> bool:
        return self.error is None


def _validate(title: str, short_message: str, detailed_message: str) -> NotifyError | None:
    fields = {"title": title, "short_message": short_message, "detailed_message": detailed_message}
    for name, value in fields.items():
        if not isinstance(value, str) or value == "":
            return NotifyError(ErrorType.VALIDATION_ERROR, f"`{name}` must be a non-empty string.")
        try:
            encoded_len = len(value.encode("utf-8"))
        except UnicodeEncodeError:
            return NotifyError(ErrorType.VALIDATION_ERROR, f"`{name}` is not valid UTF-8.")
        if encoded_len > FIELD_LIMITS[name]:
            limit = FIELD_LIMITS[name]
            return NotifyError(
                ErrorType.VALIDATION_ERROR,
                f"`{name}` exceeds the {limit}-byte UTF-8 limit.",
            )
    return None


async def notify(
    title: str,
    short_message: str,
    detailed_message: str,
    *,
    token_store: TokenStore,
    fcm_sender: FcmSender,
) -> NotifyResult:
    """Validate the payload, read the device token, and push a data-only FCM message."""
    if (err := _validate(title, short_message, detailed_message)) is not None:
        return NotifyResult(None, err)

    try:
        device_token = await token_store.read()
    except NoDeviceEnrolledError:
        return NotifyResult(
            None,
            NotifyError(
                ErrorType.NO_DEVICE_ENROLLED,
                "No device token enrolled. Enroll a device via POST /enroll first.",
            ),
        )
    except StoreUnavailableError as exc:
        return NotifyResult(None, NotifyError(ErrorType.STORE_UNAVAILABLE, str(exc)))
    except Exception as exc:  # unexpected store failure → still store-unavailable (retryable)
        return NotifyResult(None, NotifyError(ErrorType.STORE_UNAVAILABLE, str(exc)))

    # AD-2: data-only message. Exactly these three keys, nothing else.
    data = {
        "title": title,
        "short_message": short_message,
        "detailed_message": detailed_message,
    }

    try:
        message_id = await fcm_sender.send(device_token, data)
    except FcmError as exc:
        return NotifyResult(None, exc.notify_error)
    except Exception as exc:  # unclassified transport failure → retryable network error
        return NotifyResult(
            None,
            NotifyError(ErrorType.NETWORK_ERROR, f"Unexpected error sending to FCM: {exc}"),
        )

    return NotifyResult(message_id, None)
