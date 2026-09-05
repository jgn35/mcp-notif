---
id: SPEC-mcp-notif
companions:
  - ../../planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/SOLUTION-DESIGN.md
sources:
  - ../../planning-artifacts/briefs/brief-mcp-notif-2026-09-04/brief.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# mcp-notif — LLM-Driven Push Notification Infrastructure

## Why

**A pain to solve.** Checking a todo-list by hand is daily friction: open the app, scan tasks, decide what matters today. Existing reminder apps send static notifications ("3 tasks due") with no analysis, no context, no sense of priority or blockers. The ones that connect to an LLM put it behind a paywall.

mcp-notif inverts the model: the LLM is the motor, not a feature. A scheduler in the LLM's cloud service interrogates existing MCP connectors (todo-list), analyzes the result, and formulates a contextualized notification. It calls a self-hosted MCP server's `notify` tool, which bridges to Firebase Cloud Messaging and lands on an Android device. The user gets a nudge that says something useful, not a raw dump.

Personal project, monouser, self-hosted. The notification infrastructure is general by construction — any LLM can push any message — but the todo-list is the first use case because the MCP connectors already exist.

## Capabilities

- **CAP-1**
  - **intent:** An LLM can push a notification to the Android device by calling the MCP server's `notify` tool with a title, short message, and detailed message.
  - **success:** A `notify` call with three non-empty string fields results in an FCM data-only message delivered to the Android device.

- **CAP-2**
  - **intent:** The MCP server rejects invalid input before sending to FCM so the LLM gets a fast, local error instead of a silent FCM rejection.
  - **success:** A `notify` call with a missing field, an empty field, or a field exceeding its byte limit (title > 100, short_message > 500, detailed_message > 3500) returns a `validation_error` without contacting FCM.

- **CAP-3**
  - **intent:** The MCP server authenticates incoming requests so the internet-exposed endpoint is not open.
  - **success:** A request without a valid `Authorization: Bearer <token>` header matching `MCP_AUTH_TOKEN` receives HTTP 401; a request with the correct token proceeds normally.

- **CAP-4**
  - **intent:** The MCP server returns structured, typed errors on FCM push failure so the LLM can distinguish retry-safe from retry-pointless failures.
  - **success:** When FCM returns an error or the token store is inaccessible, the `notify` tool response includes an `error.type` from the fixed set (`validation_error`, `no_device_enrolled`, `store_unavailable`, `fcm_unregistered`, `fcm_invalid_argument`, `fcm_permission_denied`, `fcm_throttled`, `fcm_internal`, `network_error`) and a human-readable `message`. The type encodes retry vs. skip semantics. Success returns the FCM message ID.

- **CAP-5**
  - **intent:** The MCP server runs as a containerized service behind TLS with minimal persistence so it can be deployed and restarted without session affinity while retaining the enrolled device token.
  - **success:** The MCP server runs in a Podman container, listens on localhost, receives traffic from an existing Apache reverse proxy that terminates TLS, holds no session state between calls, and survives a restart with the device token intact (SQLite on a volume mount).

- **CAP-6**
  - **intent:** The Android app receives FCM data-only messages and displays a system notification with the title and short message in full.
  - **success:** An FCM data-only message arrives on the device; `FirebaseMessagingService.onMessageReceived` fires in both foreground and background; the system notification shows the title as the notification title and `short_message` as the body via `NotificationCompat.BigTextStyle` (full text, no truncation).

- **CAP-7**
  - **intent:** The user can read the detailed message by tapping the notification.
  - **success:** Tapping the notification opens a detail view displaying `detailed_message` as full text.

- **CAP-8**
  - **intent:** The Android app automatically registers its FCM device token with the MCP server so the server always has a valid delivery target without manual configuration.
  - **success:** On first launch the app generates an FCM token and POSTs it to the MCP server's `/enroll` endpoint. On token rotation (`onNewToken`), the app re-enrolls. When the token is stale, FCM returns 404 and the MCP server propagates `fcm_unregistered` to the LLM.

- **CAP-9**
  - **intent:** The MCP server accepts and persists the FCM device token from the Android app so the notify tool can target the correct device without manual env var configuration.
  - **success:** A `POST /enroll` with a valid `ENROLLMENT_TOKEN` bearer token and a `device_token` field writes the token to the SQLite store (overwrite — last enrollment wins); a request without the correct `ENROLLMENT_TOKEN` receives HTTP 401; a request with a missing `device_token` receives HTTP 400. The next `notify` call reads the stored token from SQLite and sends via FCM successfully.

## Constraints

- Self-hosted in a Podman container, internet-exposed. Server: Python 3.12+ async with FastMCP 4.x. Android app: Kotlin latest stable.
- Monouser, single device. No multi-user, no accounts, no multi-device in V1.
- FCM **data-only** messages (not data+notification) to guarantee `onMessageReceived` fires in all app states.
- MCP server holds no session state but persists the current FCM device token in a SQLite file (single table, single row, WAL mode, volume-mounted). No notification history, no multi-user state. Aligns with MCP 2026-07-28 stateless Streamable HTTP protocol.
- Notify path is one-way: `LLM -> MCP server -> FCM -> Android app`. The Android app additionally calls `POST /enroll` on the MCP server for token registration/rotation only. No other back-channel.
- TLS terminated by an existing Apache reverse proxy. The MCP server listens on localhost inside the container and never handles TLS directly.
- FCM HTTP v1 requires service account credentials (OAuth2). No bare API keys. firebase-admin Python SDK 7.5.0 handles token acquisition.
- FCM 4 KB total data payload limit. Field byte limits (title <= 100, short_message <= 500, detailed_message <= 3500) account for this with headroom.
- Configuration via environment variables for the MCP server (`FCM_SERVICE_ACCOUNT_PATH`, `MCP_AUTH_TOKEN`, `ENROLLMENT_TOKEN`, `TOKEN_DB_PATH` — optional, default `/data/device_token.db`). `google-services.json` for Android. FCM device token received dynamically via the `/enroll` endpoint — no manual env var configuration.
- Hexagonal architecture (ports & adapters) for the MCP server. The `notify` tool logic is the application core; MCP Streamable HTTP is the primary inbound adapter; `POST /enroll` is the second inbound adapter (plain HTTP, not MCP); the FCM sender is the primary outbound adapter; the SQLite token store is the second outbound adapter.
- Two separate auth paths on the MCP server, both using bearer tokens in the `Authorization` header: the `notify` tool uses `MCP_AUTH_TOKEN` for the LLM; the `/enroll` endpoint uses `ENROLLMENT_TOKEN` for the Android app. Different credentials so they can rotate independently.

## Non-goals

- No notification actions (mark done, snooze, reply to LLM).
- No notification history in the app or server.
- No multi-user, multi-device, or account support.
- No retry or dead-letter queue in the MCP server — the LLM owns retry decisions.
- No rate limiting, mTLS, or OAuth2 server.
- No log aggregation or file-based logging — structured JSON to stdout only.
- No health-check endpoint.

## Success signal

The LLM calls `notify` with a formulated message. The notification arrives on the Android device — title and short message visible in the notification, detailed message readable on tap — delivered through a self-hosted MCP server behind TLS with the device token enrolled automatically via `/enroll`. The user stops checking the todo-list manually because the nudge arrives proactively and says something useful.

## Assumptions

- Static bearer token auth is sufficient for a V1 monouser internet-exposed server. No mTLS, no OAuth2 server, no rate limiting.
- No retry or dead-letter queue in V1. FCM is generally reliable; the LLM handles retry based on error type.
- Android minimum API version is deferred to the Android build — not specified in the brief or architecture.
- Android app internal architecture (Activity structure, detail view implementation, lifecycle) is deferred to the Android build.

## Open Questions

_None._
