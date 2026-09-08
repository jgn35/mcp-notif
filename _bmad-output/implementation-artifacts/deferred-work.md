# Deferred Work

- source_spec: `_bmad-output/implementation-artifacts/spec-android-fcm-receiver.md`
  summary: Add an Android test suite verifying enrollment body/auth, retry classification, and FCM key handling.
  evidence: The Android app has no tests (no JVM/Robolectric suite). The build host has no JDK/Android SDK/Gradle, so no test can run in this environment; the spec's `## Verification` section accepted static-inspection verification with tests deferred to the user's build host. Three verification gaps (Review Triage Log V1/V2/V3, all high): (1) a JVM test that the `POST /enroll` body equals `{"device_token": "<token>"}` and the `Authorization` header is `Bearer <ENROLLMENT_TOKEN>`; (2) a JVM test that 401 stops after 1 attempt and 503 retries to MAX_ATTEMPTS; (3) a Robolectric test of `McpNotifMessagingService.onMessageReceived` (reads only title/short_message/detailed_message, falls back to short_message in the detail intent, skips messages missing required keys). These would settle whether the client matches the server's accept contract, not just its reject contract.
- source_spec: `_bmad-output/implementation-artifacts/spec-android-fcm-test-suite.md`
  summary: Fix `notificationId()` millisecond collision — two FCM messages in the same millisecond overwrite each other.
  evidence: Pre-existing from the receiver spec; `System.currentTimeMillis().toInt()` can collide. An AtomicInteger counter would be collision-safe. Low severity — FCM messages in the same millisecond are extremely rare.
- source_spec: `_bmad-output/implementation-artifacts/spec-android-fcm-test-suite.md`
  summary: Cancel service `scope` in `onDestroy` to prevent coroutine leak when `onNewToken` enrollment is in flight.
  evidence: Pre-existing; already triaged as reject (item J) in the receiver spec. Coroutines are short-lived and the service is app-lifetime; the leak is minimal. Low severity.

## Deferred from: code review of spec-mcp-notify-server (2026-09-08)

- `app.py:59` module-level `app = create_app()` executes side effects at import. Pre-existing; `create_app()` factory allows test injection, so tests can avoid the module-level app.
- `mcp_transport.py:27` auth disabled when `mcp_auth_token` is empty. Pre-existing; guarded by `cfg.require_auth_tokens()` in lifespan startup.
