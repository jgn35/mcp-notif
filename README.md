# mcp-notif

LLM-driven push notification system. An LLM decides when and what to notify; a
self-hosted MCP server bridges the LLM to Firebase Cloud Messaging; an Android
app receives and displays the notification.

This repo currently contains:

- **`mcp-server/`** — the MCP notification server (Python, FastMCP 4.x). Built
  and tested; see its section below.
- **`android-app/`** — the Android receiver app (Kotlin). Receives data-only
  FCM messages and enrolls its device token; see its section below.
- **`_bmad-output/`** — BMAD planning artifacts (product brief, solution design)
  and implementation artifacts (spec, sprint status). The authoritative design
  lives in
  `_bmad-output/planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/SOLUTION-DESIGN.md`.
- **`_bmad/`**, **`.agents/`** — BMAD workflow tooling and skill definitions.
  Not application code; safe to ignore when working on the server.

Firebase/FCM project setup (`google-services.json`) and Podman/Apache
deployment remain deferred to separate, per-environment builds (V1 scope is
single-user, single-device, self-hosted).

## Architecture (one line)

```
LLM --notify(tool)--> MCP server --data-only FCM--> Android app
Android app --POST /enroll--> MCP server --INSERT OR REPLACE--> SQLite token store
```

The MCP server knows nothing about todo-lists, scheduling, or business logic.
It exposes one `notify` tool (title, short_message, detailed_message) and one
plain-HTTP `POST /enroll` endpoint that persists the device token.

## mcp-server

Python >=3.12 async server, hexagonal (ports & adapters). Stack: FastMCP 4.x,
firebase-admin 7.5, SQLite (stdlib), uvicorn, uv for deps/tests.

### Layout

```
mcp-server/
  src/mcp_notif/
    config.py                        env vars (4) + fail-fast on missing auth tokens
    errors.py                        ErrorType enum + retryable set + NotifyError
    ports.py                         TokenStore / FcmSender Protocols + domain exceptions
    core/notify.py                   validate 3 fields (byte limits) -> read token -> data-only FCM
    adapters/outbound/token_store.py SQLite single-row (id=1), WAL, busy_timeout=5000
    adapters/outbound/fcm_sender.py  firebase-admin sender, status -> ErrorType mapping
    adapters/inbound/mcp_transport.py FastMCP notify tool, StaticTokenVerifier auth
    adapters/inbound/enroll.py       POST /enroll (Starlette), ENROLLMENT_TOKEN auth
    logging.py                       one JSON line per notify call to stdout
    app.py                           assembles the ASGI app, startup table creation
  tests/                             pytest (57 tests), fake FCM sender, no live creds
  Containerfile                       Podman image (python:3.12-slim, uv, port 8080)
  .dockerignore
  pyproject.toml                      uv project + deps + dev deps + ruff config
```

### Contracts

**`notify` tool** — three string fields, validated by UTF-8 byte length before
any FCM call:

| Field              | Max bytes | Required |
|--------------------|-----------|----------|
| `title`            | 100       | non-empty |
| `short_message`    | 500       | non-empty |
| `detailed_message` | 3500      | non-empty (Markdown, rendered by the Android app) |

Returns `{"message_id": "..."}` on success, or
`{"error": {"type": ..., "message": ...}}` on failure. The server never retries;
the LLM decides retry vs. skip from `error.type`.

`detailed_message` supports Markdown (headings, bold, italic, lists, code blocks,
links, tables, strikethrough). The Android app renders it as formatted text in the
detail view. `short_message` is shown as plain text in the system notification.

**`POST /enroll`** — `Authorization: Bearer <ENROLLMENT_TOKEN>`,
body `{"device_token": "<str>"}`. 200 `{"status":"enrolled"}` (overwrites the
single row), 401 on bad token, 400 on missing/empty/extra fields. Separate from
`MCP_AUTH_TOKEN` so the two rotate independently.

**Error types** (returned to the LLM):

| type                    | retry? | source                          |
|-------------------------|--------|---------------------------------|
| `validation_error`      | no     | field validation                |
| `no_device_enrolled`    | no     | token store empty/missing       |
| `store_unavailable`     | yes    | SQLite corrupt/locked           |
| `fcm_unregistered`      | no     | FCM 404 (token invalid)          |
| `fcm_invalid_argument`  | no     | FCM 400                         |
| `fcm_permission_denied` | no     | FCM 403 / service account        |
| `fcm_throttled`         | yes    | FCM 429                         |
| `fcm_internal`          | yes    | FCM 5xx                         |
| `network_error`         | yes    | unreachable / transport          |

### Configuration

| Env var                    | Purpose                                          | Default                  |
|----------------------------|--------------------------------------------------|--------------------------|
| `FCM_SERVICE_ACCOUNT_PATH` | Path to Firebase service account JSON            | (required to send)       |
| `MCP_AUTH_TOKEN`            | Bearer token for the LLM (notify tool)           | (required at startup)    |
| `ENROLLMENT_TOKEN`          | Bearer token for the Android app (enroll)         | (required at startup)    |
| `TOKEN_DB_PATH`             | SQLite token store path                           | `/data/device_token.db`  |

### Run

```bash
cd mcp-server
uv sync --extra dev

# Run locally (env vars required):
MCP_AUTH_TOKEN=... ENROLLMENT_TOKEN=... FCM_SERVICE_ACCOUNT_PATH=... \
  uv run uvicorn mcp_notif.app:app --host 127.0.0.1 --port 8080
```

The MCP endpoint is at `http://127.0.0.1:8080/mcp`; the Android app posts to
`http://<host>/enroll`. In production an existing Apache reverse proxy
terminates TLS in front of the Podman container; the server never handles TLS.

### Test

```bash
cd mcp-server
uv run pytest -q      # 57 tests, no network, no real FCM credentials
uv run ruff check .   # lint
```

Tests inject a `FakeFcmSender` and use real `firebase-admin` exception classes
for the error-mapping table, so they never touch the network or Google
credentials.

## android-app

Kotlin receiver app (minSdk 26 / target 35). It does two things: receives
data-only FCM messages and displays them, and enrolls its FCM device token
with the MCP server. V1 is read-only — no in-app actions, no notification
history, single device.

### Layout

```
android-app/
  settings.gradle.kts               Gradle Kotlin-DSL project (root)
  build.gradle.kts                   plugin versions (AGP, Kotlin, google-services)
  gradle.properties
  gradle/wrapper/gradle-wrapper.properties   wrapper version (jar regenerated by AS)
  local.properties.example           template for the two enrollment config values
  .gitignore                         ignores local.properties, google-services.json, build/
  app/
    build.gradle.kts                 reads local.properties -> BuildConfig.ENROLL_URL/_TOKEN
    proguard-rules.pro
    src/main/
      AndroidManifest.xml            INTERNET + POST_NOTIFICATIONS, service + activities
      java/com/jgn/mcpnotif/
        McpNotifApplication.kt       notification channel + first-launch enrollment
        Enrollment.kt                 fetch FCM token + POST /enroll (fire-and-forget)
        EnrollmentClient.kt          POST /enroll via HttpURLConnection, retry/backoff
        EnrollmentState.kt            in-memory status read by MainActivity
        McpNotifMessagingService.kt   onMessageReceived -> BigTextStyle; onNewToken -> re-enroll
        MainActivity.kt               enrollment status screen + manual Re-enroll
        DetailActivity.kt            renders detailed_message as Markdown (fallback: short_message)
      res/
        layout/activity_main.xml     status + endpoint + FCM token + error + re-enroll button
        layout/activity_detail.xml    title + scrollable Markdown detailed message
        drawable/ic_launcher.xml      app icon (vector)
        drawable/ic_notification.xml  notification small icon (vector)
        values/strings.xml           app name, channel id/name, status + token labels
        values/themes.xml            Theme.McpNotif (AppCompat DayNight)
        values/colors.xml            launcher background
```

### Contracts the app honors

- **FCM receive:** reads only `title`, `short_message`, `detailed_message`
  from `remoteMessage.data`; ignores any other keys. Builds the notification
  in `onMessageReceived` (data-only handling — fires in foreground and
  background). Tap opens `DetailActivity` with `detailed_message` (falls back
  to `short_message` if absent), rendered as Markdown.
- **Enrollment:** `POST /enroll` with `Authorization: Bearer <ENROLLMENT_TOKEN>`,
  body exactly `{"device_token": "<str>"}`. Retries transient failures
  (network, 5xx) with exponential backoff; stops on 400/401 (bad body / bad
  token — won't succeed by repeating). `onNewToken` re-enrolls; the server
  overwrites the single row.

### Configuration

The app reads two values at build time from `android-app/local.properties`
(git-ignored, per-machine — copy `local.properties.example`):

| Property               | Purpose                                   |
|------------------------|-------------------------------------------|
| `mcpNotif.enrollUrl`   | HTTPS endpoint of the MCP server (Apache TLS; not :8080) |
| `mcpNotif.enrollToken` | the `ENROLLMENT_TOKEN` set on the MCP server |

A missing value fails the Gradle build with a clear message. `mcpNotif.enrollUrl`
must be `https://` — the build fails otherwise, so the `ENROLLMENT_TOKEN` is never
sent over plaintext. Firebase config comes from `app/google-services.json` (also
git-ignored — drop in your own from the Firebase console; the package must match
`applicationId` = `com.jgn.mcpnotif`, or rename both).

### Build

This repo has no committed Gradle wrapper jar (it is binary); Android Studio
regenerates it on first sync, or run `gradle wrapper` once if you have Gradle
installed.

```bash
cd android-app
cp local.properties.example local.properties   # then edit the two values
# drop your Firebase google-services.json into app/
./gradlew assembleDebug        # or open in Android Studio and sync
./gradlew testDebugUnitTest   # 20 JVM unit tests (no emulator needed)
```

The Android test suite covers enrollment request shape and auth header, retry
classification (401 stops, 503 retries to max), and FCM data-key selection with
fallback. Tests run as plain JVM unit tests — no emulator or Robolectric needed.

## Status

The MCP server spec is `done` (implemented + reviewed):
`_bmad-output/implementation-artifacts/spec-mcp-notify-server.md`.
The Android receiver app spec is `done`:
`_bmad-output/implementation-artifacts/spec-android-fcm-receiver.md`.
The Android test suite spec is `in-progress`:
`_bmad-output/implementation-artifacts/spec-android-fcm-test-suite.md`.

Deferred (separate, per-environment builds): Firebase/FCM project setup
(`google-services.json`), Podman/Apache deployment.
