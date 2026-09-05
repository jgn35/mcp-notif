# Rubric-Walker Review — mcp-notif Architecture Spine (Update Pass)

**Reviewer:** rubric-walker (automated checklist)
**Date:** 2026-09-04
**Verdict:** pass-with-findings

## Findings

### Finding 1 — Medium: Deferred table contradicts AD-11 on token rotation
Deferred lists "Token rotation" but AD-11 decides it (onNewToken → re-enroll).

### Finding 2 — Medium: FastMCP serving non-MCP HTTP endpoint unverified
AD-12 assumes FastMCP 4.x can serve POST /enroll alongside MCP transport.

### Finding 3 — Low: AD-4 "every request" ambiguous vs AD-12 separate token
### Finding 4 — Low: "Manual reconfiguration" fallback undefined (AD-7 removed env-var path)
### Finding 5 — Low: SQLite corruption handling unspecified in AD-13
