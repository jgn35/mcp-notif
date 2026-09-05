# Adversarial Architecture Review — mcp-notif (Enrollment Flow Pass)

**Reviewer:** adversarial (red-team)
**Date:** 2026-09-04
**Verdict:** pass-with-findings

## Findings

### Finding 1 — Critical: Concurrent enrollment-overwrite during notify
No locking/WAL/serialization between enrollment writer and notify reader. Stale token sent → fcm_unregistered ("do not retry") when retry would succeed.

### Finding 2 — Critical: SQLITE_BUSY undefined error path
AD-8's 7 types don't cover local DB failures. Two compliant impls return different types.

### Finding 3 — High: "No device enrolled" mapped to validation_error breaks AD-8 semantics
### Finding 4 — High: Table creation ownership unspecified — "file exists, table missing" unhandled
### Finding 5 — Medium: AD-3 persistence boundary allows additional tables
### Finding 6 — Medium: enrolled_at format under-specified, dead data
### Finding 7 — Low: Hexagonal bypass — enrollment writes to DB without core mediation
