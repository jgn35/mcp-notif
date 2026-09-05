"""Enumerated error types returned to the LLM.

Mirrors the Solution Design error table (AD-8). The LLM decides retry vs. skip
from `error.type`; the server never retries on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorType(StrEnum):
    VALIDATION_ERROR = "validation_error"
    NO_DEVICE_ENROLLED = "no_device_enrolled"
    STORE_UNAVAILABLE = "store_unavailable"
    FCM_UNREGISTERED = "fcm_unregistered"
    FCM_INVALID_ARGUMENT = "fcm_invalid_argument"
    FCM_PERMISSION_DENIED = "fcm_permission_denied"
    FCM_THROTTLED = "fcm_throttled"
    FCM_INTERNAL = "fcm_internal"
    NETWORK_ERROR = "network_error"


# Error types the LLM may retry after backoff. Everything else is terminal.
RETRYABLE: frozenset[ErrorType] = frozenset(
    {
        ErrorType.STORE_UNAVAILABLE,
        ErrorType.FCM_THROTTLED,
        ErrorType.FCM_INTERNAL,
        ErrorType.NETWORK_ERROR,
    }
)


@dataclass(frozen=True)
class NotifyError:
    """A structured error returned to the LLM in place of a message_id."""

    type: ErrorType
    message: str

    @property
    def retryable(self) -> bool:
        return self.type in RETRYABLE

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {"error": {"type": self.type.value, "message": self.message}}
