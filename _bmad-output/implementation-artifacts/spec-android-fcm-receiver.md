---
title: 'Android FCM receiver app'
type: 'feature'
created: '2026-09-06'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '7ecd707cc3e9f03b46036c27a298ef0f676abb8f'
context:
  - /home/jgn/mcp-notif/_bmad-output/planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/SOLUTION-DESIGN.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The MCP notification server is built and tested, but its receiving
end does not exist: the README and solution design list the Android receiver app
as deferred. Without it, `notify` pushes to FCM with nothing to display the
message, and no device ever enrolls a token — the system chain is incomplete.

**Approach:** Build a minimal Kotlin Android app under `android-app/` that (1)
receives data-only FCM messages carrying `title` / `short_message` /
`detailed_message`, posts a system notification (BigTextStyle) and, on tap, opens
a detail Activity showing `detailed_message`; and (2) enrolls its FCM device
token by `POST /enroll` to the MCP server on first launch and on token rotation
(`onNewToken`), retrying with backoff on failure. V1 is read-only: no in-app
actions, no notification history, single device.

## Boundaries & Constraints

**Always:**
- Consume only the three FCM data keys `title`, `short_message`,
  `detailed_message`; ignore any other data keys (matches SOLUTION-DESIGN AD-2,
  and the server never sends extras).
- Enrollment is the only back-channel to the MCP server: `POST /enroll` with
  `Authorization: Bearer <ENROLLMENT_TOKEN>`, body `{"device_token": "<str>"}`
  — exactly one key, no extras (server rejects extra keys with 400).
- Data-only FCM handling: build the notification in
  `FirebaseMessagingService.onMessageReceived` so it fires in foreground AND
  background (do not rely on a `notification` payload — the server sends none).
- Notification channel required (API 26+); `minSdk = 26`. Use one channel,
  `IMPORTANCE_DEFAULT`.
- Keep `google-services.json` out of VCS (user supplies their own Firebase
  project file); keep `ENROLLMENT_TOKEN` and the enrollment endpoint URL out of
  VCS via gradle properties / `local.properties` → `BuildConfig`.

**Never:**
- No notification actions, reply, snooze, or "mark done" (V2).
- No in-app notification history or list (V2).
- No MCP client / `notify` calls from the app — the app never sends
  notifications, only enrolls.
- Do not modify `mcp-server/` or its tests; the server contract is fixed.
- Do not add a `notification` key to anything; do not persist the device token
  locally beyond what Firebase SDK does itself.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Behavior | Error Handling |
|----------|--------------|-------------------|----------------|
| First launch | No token yet | Firebase SDK yields token; app POSTs /enroll; 200 | On 401/400/network: retry with backoff, surface in UI |
| Notification received (bg) | data-only FCM with 3 keys | `onMessageReceived` posts BigTextStyle notification | If a key is missing, skip that notification (defensive) |
| Notification tap | user taps | detail Activity opens with `detailed_message` | If `detailed_message` missing, show `short_message` |
| Token rotation | `onNewToken` fires | POST /enroll with new token (overwrite) | Same retry/backoff as first launch |
| Enrollment 400 | server rejects body | Stop retrying that token; show error in UI | Do not infinite-loop |
| Enrollment 401 | bad/rotated ENROLLMENT_TOKEN | Stop retrying; show "config error" in UI | Operator must fix token in app config |

## Decisions (resolved)

- **Application ID:** `com.jgn.mcpnotif`. Kotlin package root
  `com/jgn/mcpnotif`. If the user's Firebase project uses a different package,
  they rename before building.
- **Enrollment config source:** the user of the application sets the enrollment
  endpoint URL and `ENROLLMENT_TOKEN` locally. They are read from
  `android-app/local.properties` (`mcpNotif.enrollUrl`, `mcpNotif.enrollToken`)
  and injected as `BuildConfig` fields (`ENROLL_URL`, `ENROLL_TOKEN`). Neither
  value is committed; `local.properties` and `google-services.json` are
  git-ignored. A missing value fails the Gradle build with a clear message.
- **UI scope:** `MainActivity` shows enrollment status (enrolled yes/no,
  endpoint, last error, manual "Re-enroll" button) plus the `DetailActivity`
  opened from notification tap.

</frozen-after-approval>

## Code Map

- `mcp-server/src/mcp_notif/adapters/inbound/enroll.py` -- the `POST /enroll`
  contract the app must call. Auth: `Authorization: Bearer <ENROLLMENT_TOKEN>`
  (constant-time compare, lines 25-36). Body: exactly `{"device_token": "<str>"}`
  (extra/missing keys or empty token → 400, line 44-49). Responses: 200
  `{"status":"enrolled"}`, 401 empty, 400 empty (line 52). Route `/enroll`
  mounted at root (line 56; `app.py:49`).
- `mcp-server/src/mcp_notif/core/notify.py` -- the three FCM data keys and
  byte limits the app receives: `title` (100), `short_message` (500),
  `detailed_message` (3500) (lines 17-19).
- `mcp-server/src/mcp_notif/adapters/outbound/fcm_sender.py` -- confirms
  data-only `Message(data=..., fid=device_token)`, no `notification` key
  (lines 97-101). The app MUST NOT expect a `notification` payload.
- `mcp-server/src/mcp_notif/config.py` -- `ENROLLMENT_TOKEN` env var (line 7);
  server listens on port 8080 behind Apache TLS (`app.py:6`). The app posts to
  the Apache-facing HTTPS URL, not 8080 directly.
- `SOLUTION-DESIGN.md` §3.2, §5 -- FCM `onMessageReceived` steps (read
  `title`+`short_message`, BigTextStyle, PendingIntent with
  `detailed_message`), token lifecycle (onNewToken → /enroll).
- No `android-app/` directory exists yet — greenfield. Create the Gradle
  project from scratch.

## Tasks & Acceptance

**Execution:**
- [x] `android-app/settings.gradle.kts` + `android-app/build.gradle.kts` +
  `android-app/app/build.gradle.kts` -- create Gradle Kotlin-DSL project,
  Kotlin, `minSdk=26`, `compileSdk=35`, Firebase Messaging plugin, `google-services`
  plugin; read enrollment URL + `ENROLLMENT_TOKEN` from `local.properties` into
  `BuildConfig` (per Q2 answer). Rationale: project skeleton + config plumbing.
- [x] `android-app/app/src/main/AndroidManifest.xml` -- declare
  `FirebaseMessagingService`, `MainActivity` (launcher) + `DetailActivity`,
  POST_NOTIFICATIONS permission, application class. Rationale: wiring + permissions.
- [x] `android-app/app/src/main/java/.../McpNotifApplication.kt` -- on create,
  fetch FCM token and enqueue enrollment; provide entry point for `onNewToken`.
  Rationale: enrollment lifecycle owner.
- [x] `android-app/app/src/main/java/.../EnrollmentClient.kt` -- `POST /enroll`
  via `HttpURLConnection` (no extra network dep): bearer auth, exact body,
  status-code handling (200/401/400), retry with backoff for transient errors,
  no-retry for 400/401. Rationale: matches server contract exactly.
- [x] `android-app/app/src/main/java/.../McpNotifMessagingService.kt` --
  `onMessageReceived`: read 3 keys, build BigTextStyle notification on channel
  `mcp_notif_default`, PendingIntent → detail Activity with
  `detailed_message`. Ignore unknown keys. Rationale: receive + display.
- [x] `android-app/app/src/main/java/.../DetailActivity.kt` -- show
  `detailed_message` (fallback to `short_message` if absent). Rationale: tap
  destination.
- [x] `android-app/app/src/main/java/.../MainActivity.kt` -- launcher
  Activity showing enrollment status (enrolled yes/no, endpoint, last error)
  and a manual "Re-enroll" button. Rationale: debuggability for monouser setup.
- [x] `android-app/app/src/main/res/` -- notification channel name strings,
  `ic_notification` vector drawable, app icon. Rationale: required resources.
- [x] `android-app/.gitignore` -- ignore `google-services.json`,
  `local.properties`, build outputs. Rationale: keep secrets/local config out
  of VCS.
- [x] `README.md` -- update the "Android receiver app ... deferred" line and
  the architecture/source-tree sections to reflect the built app; add a short
  Android build section (drop in `google-services.json`, set `local.properties`
  values, `./gradlew assembleDebug`). Rationale: AGENTS.md requires README
  stays in sync.

**Acceptance Criteria:**
- Given a data-only FCM message with the three keys, when it arrives in
  background, then a system notification appears showing `title` and
  `short_message` (full text via BigTextStyle).
- Given the user taps the notification, when the detail Activity opens, then
  `detailed_message` is displayed (or `short_message` if detailed is absent).
- Given first launch with network, when the Firebase token is obtained, then
  the app POSTs `{"device_token": "<token>"}` to `/enroll` with the bearer
  `ENROLLMENT_TOKEN` and receives 200.
- Given `onNewToken` fires, when a rotated token is produced, then the app
  re-enrolls via the same `/enroll` call (server overwrites the row).
- Given enrollment returns 400 or 401, when the app handles it, then it stops
  retrying that attempt and surfaces the failure in the MainActivity status
  screen — no infinite retry loop.

## Implementation Notes

Environment constraint: this environment has no Android SDK, Gradle, or JDK.
The app cannot be compiled here. Implementation produces source that the user
builds on their own machine with Android Studio + their `google-services.json`.
Verification in this session is limited to static inspection (see Verification).

### What was built (2026-09-06)
Created `android-app/` as a greenfield Gradle Kotlin-DSL project (24 new
files). Stack: Kotlin 2.0.21, AGP 8.7.0, Gradle 8.10.2, Firebase BoM 33.5.1,
minSdk 26 / target 35, JDK 17, AppCompat theme. The Gradle wrapper jar is
binary and intentionally not committed; Android Studio regenerates it on
sync (documented in README).

Enrollment plumbing: `app/build.gradle.kts` reads `mcpNotif.enrollUrl` and
`mcpNotif.enrollToken` from `android-app/local.properties` (git-ignored) and
injects them as `BuildConfig.ENROLL_URL` / `BuildConfig.ENROLL_TOKEN`. A
missing value fails the build with a clear `GradleException`. A
`local.properties.example` documents the keys.

Receiving: `McpNotifMessagingService.onMessageReceived` reads only
`title` / `short_message` / `detailed_message` from `remoteMessage.data`,
ignores everything else, and defensively skips messages missing the two
required keys. Builds a `BigTextStyle` notification on channel
`mcp_notif_default` with a `PendingIntent` to `DetailActivity` carrying
`detailed_message` (falls back to `short_message`). Channel created in
`McpNotifApplication.onCreate`.

Enrollment: `EnrollmentClient` does `POST {ENROLL_URL}/enroll` via
`HttpURLConnection` with `Authorization: Bearer {ENROLL_TOKEN}` and body
exactly `{"device_token":"<escaped>"}`. Retry policy: up to 5 attempts with
exponential backoff (2s..30s cap) for transient failures (network, 5xx,
unexpected codes); no retry on 400/401/403/404. `onNewToken` re-enrolls via
the same path. `MainActivity` shows status (enrolled / enrolling / not
enrolled), the endpoint, the last error, and a manual Re-enroll button.

README updated: repo contents list, new `android-app` section (layout,
contracts, configuration, build), and Status. The "Android app deferred"
line is gone; only Firebase project setup and Podman/Apache deployment
remain deferred.

### Matrix test audit — NOT satisfied in this environment
The frozen block contains an I/O & Edge-Case Matrix (6 rows). Step-03
requires each row be covered by a test that ran and passed. There is no
Android/Kotlin test suite and no JDK / Android SDK / Gradle in this
environment, so no runnable test exists and none can be executed here. The
matrix behaviors were verified by static inspection against the server
contract in the Code Map instead — this is NOT equivalent to passing tests.
To satisfy the audit, instrumented/unit tests (e.g. a JVM test of
`EnrollmentClient` retry + body shape against a stub `HttpURLConnection`,
and a Robolectric test of `McpNotifMessagingService.onMessageReceived`)
must be written and run on a machine with the Android toolchain. This is
left to the user's build host; flagged for step-04.

## Verification

**Commands:**
- None runnable in this environment (no JDK/Android SDK/Gradle). On a machine
  with Android Studio: drop `google-services.json` into `android-app/app/`,
  set enrollment values in `android-app/local.properties`, run
  `cd android-app && ./gradlew assembleDebug` -- expected: APK builds.

**Manual checks (this session):**
- Inspect every Kotlin source against the server contract in the Code Map:
  enroll body is exactly `{"device_token": ...}`, auth header is
  `Bearer <ENROLLMENT_TOKEN>`, FCM handler reads only the 3 data keys, no
  `notification` payload is expected.
- Confirm `android-app/.gitignore` excludes `google-services.json` and
  `local.properties`.
- Confirm `README.md` no longer calls the Android app deferred.

## Review Triage Log

- A — `MainActivity` maps `State.ERROR` to `status_not_enrolled` (no distinct
  error label) — **low, patch**. The error text IS shown in the error field,
  but the status label reads "Not enrolled" for both NOT_ENROLLED and ERROR;
  the matrix row "Enrollment 401" says show "config error". Fix: add a
  `status_error` string and map ERROR to it.
- B — `Enrollment.fetchAndEnroll` wraps a callback API in a redundant outer
  coroutine — **low, patch**. The outer `scope.launch {}` adds nothing
  (`addOnCompleteListener` dispatches to main itself). Fix: remove it.
- C — `EnrollmentState` is in-memory; `onCreate` re-POSTs on every cold start
  (flicker + redundant traffic) — **low, reject**. Re-enroll-on-start is
  defensible and idempotent (server `INSERT OR REPLACE`); the fix
  (SharedPreferences flag) adds complexity beyond a direct correction.
- D — Fixed `NOTIFICATION_ID = 1001` overwrites prior notifications — **low,
  patch**. A second FCM message before the user views the first replaces it.
  Fix: a unique id per message (one line, no public surface).
- E — No HTTPS enforcement; `http://` on API 26-27 leaks the bearer token,
  and a non-HTTP scheme throws an uncaught `ClassCastException` — **medium,
  patch**. Fix: validate `mcpNotif.enrollUrl` starts with `https://` at build
  time and fail the Gradle build otherwise.
- F — `jsonEscape` omits JSON control chars below U+0020 — **low, patch**.
  FCM tokens are alphanumeric so it won't trigger, but the function is
  presented as a JSON escaper. Fix: use the platform `org.json.JSONObject`
  (no new dependency) instead of hand-rolling JSON.
- G — `errorStream` not drained on non-200 — **low, reject**. `disconnect()`
  is already called in `finally`; the claimed socket-reuse harm is marginal
  and retries are rare.
- H — No `areNotificationsEnabled()` log when `POST_NOTIFICATIONS` is denied
  on API 33+ — **low, reject**. `notify()` silently no-op'ing is expected
  when the user denies permission; the fix adds a branch for no user-facing
  benefit.
- I — `ic_launcher` is a plain vector used as `android:icon`, not an adaptive
  icon — **low, reject**. Cosmetic; the fix (mipmap-anydpi-v26 + foreground/
  background) is more than a direct correction.
- J — Service `scope` never cancelled in `onDestroy` — **low, reject**.
  Coroutines are short-lived and the service is app-lifetime; minimal leak.
- K — Concurrent enrollment races on `EnrollmentState` (last writer wins) —
  **low, reject**. `fetchAndEnroll` and `onNewToken` rarely run concurrently;
  the fix needs a `Mutex`.
- L — `local.properties` `FileInputStream` IOException uncaught (raw
  stacktrace) — **low, reject**. Rare (file exists but unreadable),
  developer-only.
- M — `when(code)` has no 2xx range (201/204 → retryable) — **false, reject**.
  The server contract returns exactly 200 (`enroll.py:52`); 201/204 is
  unreachable.
- N — Non-IOException `RuntimeException` (e.g. `SecurityException`) propagates
  — **false, reject**. `INTERNET` permission is declared; `openConnection`
  won't throw `SecurityException`.
- V1 — Verification gap: enrollment body shape + auth header unverified
  (no tests) — **high, defer**. Pre-verified by the verification-gap layer.
  The fix (a JVM test of `EnrollmentClient` against a stub
  `HttpURLConnection`/`MockWebServer`) is not trivial and adds test surface,
  so it is not a `patch`; the spec's `## Verification` section already
  accepted static-inspection verification with tests deferred to the user's
  build host. Grouped with V2/V3.
- V2 — Verification gap: retry classification (retryable vs non-retryable)
  unverified — **high, defer**. Same root cause as V1; a JVM test asserting
  401 stops after 1 attempt and 503 retries to `MAX_ATTEMPTS`. Grouped with
  V1/V3.
- V3 — Verification gap: FCM key selection + detail fallback in
  `onMessageReceived` unverified — **high, defer**. Same root cause as V1; a
  Robolectric test of `onMessageReceived` with `ShadowNotificationManager`.
  Requires the Android toolchain on the build host. Grouped with V1/V2.
