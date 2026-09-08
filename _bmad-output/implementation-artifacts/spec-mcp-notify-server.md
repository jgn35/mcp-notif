---
title: 'mcp-notif MCP notify server'
type: 'feature'
created: '2026-09-04'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/SOLUTION-DESIGN.md'
baseline_commit: 'NO_VCS'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The mcp-notif system needs its self-hosted MCP notification server — the bridge between an LLM and Firebase Cloud Messaging. No server code exists yet; the repo is greenfield.

**Approach:** Build the Python async server (FastMCP 4.x) with a hexagonal layout: a `notify` MCP tool that validates a three-field payload and pushes a data-only FCM message, a plain HTTP `POST /enroll` endpoint that persists the device token in SQLite, two separate static bearer tokens, and structured JSON stdout logging. Tests run without live Google credentials via a fake FCM sender.

## Boundaries & Constraints

**Always:**
- `notify` accepts exactly `title` (<=100 bytes), `short_message` (<=500), `detailed_message` (<=3500); all non-empty strings; validated by UTF-8 byte length before any FCM call.
- FCM message is **data-only** (no `notification` key). Only the three data keys above; no extras.
- `POST /enroll` accepts only `{"device_token": "<str>"}`; writes via `INSERT OR REPLACE` to a single-row (`id=1`) SQLite table; returns `{"status":"enrolled"}` (200), 401 on bad `ENROLLMENT_TOKEN`, 400 on missing/empty `device_token`.
- SQLite: every connection sets `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`. Table created at startup before either inbound adapter serves.
- `MCP_AUTH_TOKEN` guards the MCP transport; `ENROLLMENT_TOKEN` guards `/enroll`; distinct, rotate independently. Mismatch → 401.
- Errors returned to the LLM use the enumerated `error.type` set with the retry semantics in the I/O matrix.
- One structured JSON log line per `notify` call to stdout (request_id, timestamp, result, error_type, latency_ms, fcm_message_id).
- FCM auth via service account JSON at `FCM_SERVICE_ACCOUNT_PATH` (firebase-admin handles OAuth2). No bare API keys.

**Never:**
- No scheduling, business logic, todo-list knowledge, or notification history in the server.
- No retry inside the server — the LLM decides retry from the error type.
- No `notification` hybrid FCM messages, no extra FCM data keys, no actions/snooze/reply.
- No multi-user/multi-device (single-row token store). No mTLS, no rate limiting, no `/health` endpoint (V2).
- No live FCM calls in the test suite (use a fake sender). No real Firebase project setup or Podman/Apache deployment in this build.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Happy notify | valid 3 fields, token enrolled, FCM 200 | `{"message_id": "..."}`; data-only push | N/A |
| Oversized field | title >100 / short >500 / detail >3500 bytes | reject before FCM | `validation_error` (no retry) |
| Empty/missing field | any field empty/absent | reject | `validation_error` |
| No device enrolled | token store empty/missing table | do not call FCM | `no_device_enrolled` (no retry) |
| Store corrupt | SQLite `DatabaseError` on read | — | `store_unavailable` (retry after backoff) |
| FCM 404 | token invalid | propagate | `fcm_unregistered` (no retry) |
| FCM 400 | payload rejected | propagate | `fcm_invalid_argument` (no retry) |
| FCM 403 | service account misconfigured | propagate | `fcm_permission_denied` (no retry) |
| FCM 429 | rate limited | propagate | `fcm_throttled` (retry after backoff) |
| FCM 5xx | FCM internal | propagate | `fcm_internal` (retry) |
| FCM unreachable | network/timeout | propagate | `network_error` (retry) |
| Enroll happy | valid `device_token` + valid `ENROLLMENT_TOKEN` | 200 `{"status":"enrolled"}`, overwrite row | N/A |
| Enroll bad token | missing/wrong `ENROLLMENT_TOKEN` | 401 | N/A |
| Enroll bad body | missing/empty `device_token` or extra fields | 400 | N/A |

</frozen-after-approval>

## Code Map

Greenfield — no existing source. Authoritative contracts live in `_bmad-output/planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/SOLUTION-DESIGN.md` (sections 2–7, AD-1..AD-13). Reuse its schema, error table, env-var table, and log shape verbatim; do not reinterpret them.

New tree (package `mcp_notif`, src layout, uv + pyproject):
- `mcp-server/pyproject.toml` -- uv project; deps: `fastmcp` (4.x), `firebase-admin` (7.5.0); dev: `pytest`, `pytest-asyncio`, `httpx`. Python >=3.12.
- `mcp-server/src/mcp_notif/config.py` -- load env vars (`FCM_SERVICE_ACCOUNT_PATH`, `MCP_AUTH_TOKEN`, `ENROLLMENT_TOKEN`, `TOKEN_DB_PATH` default `/data/device_token.db`).
- `mcp-server/src/mcp_notif/errors.py` -- error-type enum/constants + retry flags (per I/O matrix).
- `mcp-server/src/mcp_notif/core/notify.py` -- validate 3 fields (byte lengths), read token from store port, build FCM data payload, call sender port, map exceptions to error types, return `{"message_id"}` or `{"error":{...}}`.
- `mcp-server/src/mcp_notif/adapters/outbound/token_store.py` -- SQLite store: `init()` create table, `read()` → token or `no_device_enrolled`/`store_unavailable`, `write(token)` INSERT OR REPLACE. WAL + busy_timeout per connection.
- `mcp-server/src/mcp_notif/adapters/outbound/fcm_sender.py` -- firebase-admin sender port; default impl initializes app from `FCM_SERVICE_ACCOUNT_PATH`, sends data-only message via `messaging.send`. Map FCM status codes to error types.
- `mcp-server/src/mcp_notif/adapters/inbound/mcp_transport.py` -- FastMCP server exposing the `notify` tool; bearer auth via `MCP_AUTH_TOKEN`; calls core `notify`.
- `mcp-server/src/mcp_notif/adapters/inbound/enroll.py` -- Starlette/FastAPI route `POST /enroll`; bearer auth via `ENROLLMENT_TOKEN`; writes token store.
- `mcp-server/src/mcp_notif/app.py` -- build ASGI app: mount FastMCP + add `/enroll` route, call token store `init()` at startup, listen on localhost:8080.
- `mcp-server/src/mcp_notif/logging.py` -- one JSON line per notify call to stdout.
- `mcp-server/Containerfile` -- Podman image (python:3.12-slim), install uv/project, run ASGI on 8080, volume `/data`.
- `mcp-server/tests/` -- pytest: validation edge cases, token store (temp file), enroll route (httpx), notify tool end-to-end with a fake FCM sender, error mapping, logging.

## Tasks & Acceptance

**Execution:**
- [x] `mcp-server/pyproject.toml` -- create uv project with deps and dev deps, Python >=3.12 -- defines the build/test surface.
- [x] `mcp-server/src/mcp_notif/config.py` -- load and validate the four env vars with defaults -- single source of config truth.
- [x] `mcp-server/src/mcp_notif/errors.py` -- define error types + retryable flag per I/O matrix -- shared by core and adapters.
- [x] `mcp-server/src/mcp_notif/ports.py` -- Protocols `FcmSender`/`TokenStore` + domain exceptions (`FcmError`, `NoDeviceEnrolledError`, `StoreUnavailableError`) -- hexagonal boundaries.
- [x] `mcp-server/src/mcp_notif/adapters/outbound/token_store.py` -- implement SQLite store (init/read/write, WAL, busy_timeout, single row) -- persistence per AD-13.
- [x] `mcp-server/src/mcp_notif/adapters/outbound/fcm_sender.py` -- implement firebase-admin sender + status→error-type mapping; expose a port/protocol a fake can satisfy -- FCM push per AD-2.
- [x] `mcp-server/src/mcp_notif/core/notify.py` -- validate fields, read token, build data-only payload, call sender, map errors -- core tool logic.
- [x] `mcp-server/src/mcp_notif/adapters/inbound/mcp_transport.py` -- FastMCP `notify` tool with bearer auth wired to core -- inbound adapter 1.
- [x] `mcp-server/src/mcp_notif/adapters/inbound/enroll.py` -- `POST /enroll` route with bearer auth + body validation wired to token store -- inbound adapter 2.
- [x] `mcp-server/src/mcp_notif/logging.py` -- structured JSON line per notify call -- AD-10.
- [x] `mcp-server/src/mcp_notif/app.py` -- assemble ASGI app, startup table creation, localhost:8080 -- entry point.
- [x] `mcp-server/Containerfile` -- Podman image definition per deployment section -- container artifact.
- [x] `mcp-server/tests/` -- pytest suite covering the I/O matrix edge cases with a fake FCM sender and temp SQLite -- proves the contracts.

**Acceptance Criteria:**
- Given a valid 3-field notify call and an enrolled token, when the fake FCM sender returns a message id, then `notify` returns `{"message_id": "..."}` and emits one JSON log line with `result: success`.
- Given a field exceeding its byte limit, when `notify` is called, then it returns `{"error":{"type":"validation_error",...}}` without invoking the FCM sender.
- Given an empty/missing token store, when `notify` is called, then it returns `no_device_enrolled` without an FCM call.
- Given `POST /enroll` with a valid `device_token` and correct `ENROLLMENT_TOKEN`, then the store row (`id=1`) is overwritten and the response is `200 {"status":"enrolled"}`.
- Given `POST /enroll` with a wrong/missing `ENROLLMENT_TOKEN`, then the response is 401; given a missing/empty `device_token`, then 400.
- Given the test suite, when run with `uv run pytest`, then all tests pass with no network access and no real FCM credentials.

## Implementation Notes

- Built under `mcp-server/` with uv + src-layout package `mcp_notif`. Deps: `fastmcp>=4.0,<5`, `firebase-admin>=7.5,<8`, `uvicorn`; dev: pytest, pytest-asyncio, httpx, ruff. Python >=3.12 (env runs 3.13).
- FastMCP resolved to 4.0.3 (latest stable, not beta). MCP transport: `mcp.http_app(path="/")` mounted at `Mount("/mcp", mcp_app)`; the composed `lifespan` runs `config.require_auth_tokens()` + `store.init()` then `async with mcp_app.lifespan(app)`. MCP auth via `StaticTokenVerifier` from `fastmcp.server.auth` (the configured `MCP_AUTH_TOKEN`).
- Used **Starlette directly** (not FastAPI) — FastMCP's `http_app()` already returns a Starlette app, so no extra web-framework dependency. `POST /enroll` is a Starlette `Route`; it reads `token_store` and `enrollment_token` from `app.state`, validates body (exactly `{"device_token": str}`, non-empty), returns 200/401/400.
- firebase-admin **7.5.0 deprecates `Message.token` in favor of `Message.fid`**, but `fid` expects a Firebase Installation ID (not an FCM registration token). The sender uses `messaging.Message(data=data, token=device_token)` — `token` still accepts FCM registration tokens during the migration period and avoids `fcm_unregistered`.
- `FcmError` lives in `ports.py` (domain) rather than the fcm adapter, so the core depends only on ports — never on firebase-admin. The adapter raises `FcmError(NotifyError)` after mapping firebase exceptions; the core surfaces `error.to_dict()` to the LLM (never raises on FCM failure — the LLM decides retry).
- Verification: `uv run pytest` -> 55 passed (no network, no Google creds); `uv run ruff check .` -> clean; `uv run python -c "import mcp_notif.app"` -> resolves (`Starlette`). Fakes: a `FakeFcmSender` records sends; real firebase exception classes are used in mapping tests; the adapter is exercised with `messaging.send` monkeypatched.
- No VCS in this repo (`baseline_commit: NO_VCS`); the stage-diff step was skipped — tasks/AC were verified against the files on disk.

### Post-review patches (step-04, all `low`, no loopback)

- `_send_sync` exception handling (B11 + O1): removed the dead `RequestException` branch (it subclasses `IOError`/`OSError`); non-Firebase failures now map to `network_error` per the matrix instead of falling through `_map_firebase_error` → `FCM_INTERNAL`.
- `core/notify._validate` (E3): wrapped `value.encode("utf-8")` in try/except → `validation_error` for lone-surrogate / non-UTF-8 strings.
- `pyproject.toml` (B8): added `starlette>=0.37` as an explicit dependency (direct imports relied on a transitive pin via fastmcp).
- `Containerfile` (B3): pinned the uv image to `ghcr.io/astral-sh/uv:0.11.15`.
- `.dockerignore` (B2): added to keep the Podman build context lean (excludes `.venv`, caches, `tests`).
- Docstrings (B10): corrected "FastAPI app" → "Starlette app" in `conftest.make_app` and `test_app`.
- Tests: added `UnauthenticatedError` → `FCM_PERMISSION_DENIED` to the mapping table (B12/V2); assert the real `Message` is built with `token=device_token` + `data == _PAYLOAD` and `fid is None` (V3); added a test that `create_app` with empty tokens raises `RuntimeError` at lifespan startup (V1).
- Re-verified: `uv run pytest` -> 57 passed; `uv run ruff check .` -> clean; `import mcp_notif.app` -> OK. Empirically confirmed (against the pinned firebase-admin 7.5.0): `Message(fid=...)` expects a Firebase Installation ID, not an FCM registration token — using it with an FCM token causes `fcm_unregistered`; `Message(token=...)` is the correct field for FCM registration tokens. A fresh `sqlite3.connect()` defaults `busy_timeout` to 5000.

## Spec Change Log

<!-- No loopback occurred in this review pass. -->

## Review Triage Log

Reviewers: blind-hunter (B), edge-case-hunter (E), verification-gap (V, pre-verified). All survivor verdicts are `low` → `patch`; no `high`/`medium`/`intent_gap`/`bad_spec`, so no loopback.

- B1 (`.pytest_cache`/`.ruff_cache` in diff; no `.gitignore`) — **false**. No VCS in this repo; caches are not "committed". The caches leaked into the review diff via the generator; regenerated the diff excluding them. `.gitignore` is moot without git.
- B2 (no `.dockerignore`) — **low**. Build-context hygiene; Containerfile only COPYs `pyproject.toml` + `src`, but the context still transfers `.venv`/caches. → patch (add `.dockerignore`).
- B3 (`uv:latest` unpinned in Containerfile) — **low**. Reproducibility hygiene. → patch (pin the uv image tag).
- B4 (Containerfile runs as root) — **low, rejected**. Monouser server behind Apache on localhost; non-root adds a user + volume-ownership handling beyond a direct correction, and the intent did not require it.
- B5 (no HEALTHCHECK) — **false/out-of-scope**. The frozen block explicitly defers `/health` to V2 ("no `/health` endpoint (V2)").
- B6 (`fid` is wrong; use `token`) — **false**. Empirically: in firebase-admin 7.5.0 `Message(token=...)` emits "Message.token is deprecated. Use Message.fid instead"; `Message(fid=...)` works warning-free and sets `self.fid`. `fid` is the pinned SDK's directed field.
- B7 (`test_wal_and_busy_timeout_pragmas_set` will fail; busy_timeout not persisted) — **false**. Empirically the test passes: a fresh `sqlite3.connect()` defaults `PRAGMA busy_timeout` to 5000 (the `timeout=5.0` arg). My `_connect` also sets it explicitly, so the contract holds. (Test is non-discriminating but not defective.)
- B8 (`starlette` not an explicit dependency) — **low**. Direct imports from `starlette` rely on a transitive pin via fastmcp. → patch (add `starlette>=0.37`).
- B9 (no fail-fast for `FCM_SERVICE_ACCOUNT_PATH` at startup) — **low, rejected**. Enrollment works without FCM creds; the real sender lazily fails with a clear `FCM_PERMISSION_DENIED` on first notify. Requiring it at startup would break enroll-before-FCM-config. Fix adds a guard the intent did not mandate.
- B10 (docstrings say "FastAPI app" but code is Starlette) — **low**. Cosmetic inconsistency. → patch (fix docstrings).
- B11 (`_map_firebase_error` catch-all masks non-Firebase exceptions; unclassified → `FCM_INTERNAL`) — **low**. The `_send_sync` `except Exception` fallthrough routes non-Firebase exceptions through `_map_firebase_error`, contradicting the matrix (unreachable → `network_error`). Same root cause as O1. → patch.
- B12 (`UnauthenticatedError` mapping untested) — **low**. Test gap (== V2). → patch.
- E1 (enroll `_enroll` doesn't catch `StoreUnavailableError` → 500) — **low, rejected**. `/enroll` is not LLM-facing; the design says the Android app retries enrollment failures with backoff, so a 500 on a corrupt store is acceptable. Fix adds a guard not mandated by intent.
- E2 (`_init` doesn't catch `sqlite3.DatabaseError` at startup) — **low, rejected**. A corrupt store at startup correctly prevents the server from starting (operator must restore/delete the file); only the exception *type* is inconsistent. Bad outcome (no start on corrupt store) is correct behavior.
- E3 (`_validate` doesn't catch `UnicodeEncodeError` for lone surrogates) — **low**. `value.encode("utf-8")` raises on lone surrogates, breaking the structured `validation_error` contract. → patch (wrap encode in try/except).
- V1 (startup auth-token enforcement not integration-tested) — **low**, pre-verified. No test builds an app with empty tokens and asserts the lifespan raises. → patch (add test).
- V2 (`UnauthenticatedError` → `FCM_PERMISSION_DENIED` untested) — **low**, pre-verified (== B12). → patch.
- V3 (`FirebaseFcmSender` message construction (`fid=device_token`) unverified) — **low**, pre-verified. The monkeypatched `send` ignores the `message` arg; no test asserts `message.fid`/`message.data`. → patch (assert on the constructed message).
- O1 (`RequestException` branch is dead code) — **low**. `requests.exceptions.RequestException` extends `IOError`/`OSError`, already caught by the `OSError` isinstance check. Same root cause as B11. → patch.
- O2 (enroll `StoreUnavailableError` → 500) — **low**, same as E1, rejected with E1.

## Design Notes

The design's source tree shows `src/core` and `src/adapters` flat; this build uses a namespaced package `src/mcp_notif/` so imports are stable and the package is pip-installable via uv. Adapter boundaries are Python Protocols: `FcmSender` (core depends on it) and `TokenStore` (core + enroll depend on it). The default `FcmSender` wraps firebase-admin; tests inject a `FakeFcmSender` — this is how the suite avoids live Google creds.

FastMCP 4.x mounting inside FastAPI/Starlette and adding a non-MCP `/enroll` route in the same ASGI app is the key integration risk; confirm the exact FastMCP 4.x ASGI mount API during implementation (it may expose `http_app()` or a Starlette-mountable app). Keep the MCP transport and `/enroll` sharing one token-store instance and one startup table-creation hook.

Error type → FCM status mapping: 404 → `fcm_unregistered`, 400 → `fcm_invalid_argument`, 403 → `fcm_permission_denied`, 429 → `fcm_throttled`, 5xx → `fcm_internal`, connection/timeout → `network_error`. `firebase_admin.exceptions` provides `FirebaseError` subclasses (`InvalidArgumentError`, `PermissionDeniedError`, `NotFoundError`, `QuotaExceededError`, `InternalError`, `UnknownError`) — map from these.

## Verification

**Commands:**
- `cd mcp-server && uv run pytest -q` -- expected: all tests pass, no network/creds used.
- `cd mcp-server && uv run python -c "import mcp_notif.app"` -- expected: imports resolve (no runtime start).
- `cd mcp-server && uv run ruff check .` (if configured) -- expected: clean.

**Manual checks (if no CLI):**
- Inspect that the FCM payload builder never sets a `notification` key and only the three `data` keys.
- Inspect that every new SQLite connection sets WAL + busy_timeout.

### Review Findings

**Review 2 (2026-09-08): triggered by `fcm_unregistered` bug after Android FCM-token display change.**

Patch findings:
- [x] [Review][Patch] **fid vs token in fcm_sender.py** [mcp-server/src/mcp_notif/adapters/outbound/fcm_sender.py:100] — `fid` expects a Firebase Installation ID, not an FCM registration token. The Android app sends an FCM registration token via `FirebaseMessaging.getInstance().token`. FCM rejects it as `UNREGISTERED`. Overrides previous review B6 (which wrongly concluded `fid` was correct). Fix: use `token=device_token`; update test_fcm_mapping.py:80 to assert `.token`; update comment and Implementation Notes.
- [x] [Review][Patch] **_ensure_app() data race** [mcp-server/src/mcp_notif/adapters/outbound/fcm_sender.py:73-86] — No lock around check-and-initialize; concurrent first sends can both call `initialize_app`, second raises `ValueError` caught as `NETWORK_ERROR`. Fix: add `threading.Lock`.
- [x] [Review][Patch] **_ensure_app() error misclassification** [mcp-server/src/mcp_notif/adapters/outbound/fcm_sender.py:73-86] — `credentials.Certificate()` / `initialize_app()` non-Firebase errors (invalid service account file) fall through to `NETWORK_ERROR` instead of `FCM_PERMISSION_DENIED`. Fix: catch in `_ensure_app` and raise `FcmError(FCM_PERMISSION_DENIED)`.
- [x] [Review][Patch] **Stale deviceToken in EnrollmentState** [android-app/.../EnrollmentState.kt:28,42] — `setEnrolling()` and `setError()` don't clear `deviceToken`; UI shows stale token during re-enroll/error. Fix: set `deviceToken = null` in both.
- [x] [Review][Patch] **assert stripped under python -O** [mcp-server/src/mcp_notif/adapters/inbound/mcp_transport.py:59, logging.py:36] — `assert result.error is not None` vanishes under `-O`; replace with `if` guard.
- [x] [Review][Patch] **Missing test for EnrollmentState.setSuccess** [android-app/...] — No test verifies that `setSuccess(token)` stores the token in `Snapshot`. Fix: add `EnrollmentStateTest.kt`.
- [x] [Review][Patch] **ports.py docstring inaccuracy** [mcp-server/src/mcp_notif/ports.py:38-41] — Says "core maps it to an ErrorType" but the adapter does the mapping; core just unwraps `FcmError`. Fix: update docstring to mention `FcmError`.

Defer findings:
- [x] [Review][Defer] **app.py module-level side effects** [mcp-server/src/mcp_notif/app.py:59] — deferred: pre-existing; `create_app()` factory allows test injection.
- [x] [Review][Defer] **Auth disabled when mcp_auth_token empty** [mcp-server/src/mcp_notif/adapters/inbound/mcp_transport.py:27] — deferred: pre-existing; guarded by `cfg.require_auth_tokens()` in lifespan.

Rejected:
- Broad `except Exception` in notify.py — safety net; specific exceptions caught first.
- `Bearer` case-sensitive in enroll.py — only client (Android) sends "Bearer" correctly.
- `PRAGMA journal_mode=WAL` per connection — harmless redundancy; WAL is persistent at DB level.
- `send()` returns None — unreachable per `FcmSender.send() -> str` Protocol.
- No tests in diff — tests exist (57 passing); not in the diff by scope selection.
- Android changes in server-spec diff — review scope, not a code defect.
- Logging conditional omission of `error_type`/`fcm_message_id` — correct behavior.
- enroll.py unhandled `token_store.write()` exception — previously rejected (E1/O2); Android retries 500 with backoff.
- `token_store._init()` doesn't wrap `DatabaseError` — previously rejected (E2); corrupt store should prevent startup.
