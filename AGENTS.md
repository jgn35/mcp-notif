# AGENTS.md

Instructions for AI agents working in this repository. Read this before
making changes.

## Project

`mcp-notif` is an LLM-driven push notification system. The implemented component
is `mcp-server/` (Python, FastMCP 4.x, hexagonal). The authoritative design is
`_bmad-output/planning-artifacts/architecture/architecture-mcp-notif-2026-09-04/SOLUTION-DESIGN.md`;
the implementation spec is
`_bmad-output/implementation-artifacts/spec-mcp-notify-server.md`.

`_bmad/` and `.agents/` are BMAD workflow tooling — not application code. Do
not modify them when working on the server.

## README is load-bearing — keep it in sync

The root `README.md` is the source of truth for: the project overview, the
`mcp-server/` layout, the `notify` / `POST /enroll` contracts, the error-type
table, env vars, and the run/test commands.

**When you change the server, update `README.md` in the same change so it stays
accurate.** Specifically, update it when you:

- add, remove, rename, or move a file under `mcp-server/src/` (update the Layout
  tree);
- change the `notify` tool fields, byte limits, or return shape (update
  Contracts);
- change `POST /enroll` request/response or status codes (update Contracts);
- add, remove, or rename an `ErrorType` (update the error-type table);
- add or rename an env var, or change a default (update Configuration);
- change the run or test commands (update Run / Test);
- change the test count materially (update the number cited in Test).

Do not let the README drift from the code. A stale README is a defect.

## Working on the server

- Python >=3.12; deps via `uv` (`uv sync --extra dev` in `mcp-server/`).
- Tests: `cd mcp-server && uv run pytest -q` (no network, no real FCM creds —
  a `FakeFcmSender` is injected).
- Lint: `cd mcp-server && uv run ruff check .` — must stay clean.
- Keep the hexagonal boundaries: the core depends only on `ports.py` Protocols,
  never on `firebase-admin` or HTTP/Starlette. Adapters translate.
- The server never retries on its own; the LLM decides retry from `error.type`.
- FCM messages are **data-only** (no `notification` key) — this is a hard
  constraint from the design.
