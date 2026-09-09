---
title: 'Android markdown rendering in detail view'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Android app's `DetailActivity` displays `detailed_message` as raw
plain text in a `TextView`. When the MCP server sends markdown-formatted content
(headings, bold, lists, code blocks, links), the user sees literal markdown syntax
(`**bold**`, `# Heading`) instead of rendered formatted text.

**Approach:** Add the Markwon library (v4.6.2, core + ext-strikethrough + ext-tables)
to the Android app and render `detailed_message` as markdown in `DetailActivity`
instead of setting it as plain text. The MCP server already passes
`detailed_message` through unchanged — no server logic change needed, only a
docstring update to document markdown support. The system notification
(`BigTextStyle`) continues to show `short_message` as plain text (Android system
notifications cannot render markdown). Update README to note markdown support.

</frozen-after-approval>

## Implementation Notes

- Added Markwon 4.6.2 dependencies (core, ext-strikethrough, ext-tables) to
  `android-app/app/build.gradle.kts`. No repository changes needed — mavenCentral()
  already configured in settings.gradle.kts.
- Modified `DetailActivity.kt`: builds a Markwon instance in onCreate with
  StrikethroughPlugin and TablePlugin, then calls `markwon.setMarkdown(textView,
  detailed)` instead of `textView.text = detailed`. The title TextView remains
  plain text.
- Updated `mcp_transport.py` notify tool docstring: `detailed_message` now notes
  "(Markdown)" and "rendered by the Android app". Wrapped to satisfy ruff 100-char
  line limit.
- Updated README.md: contracts table, notify tool description, Android layout tree
  (DetailActivity description, activity_detail.xml description), and app contracts
  section all note Markdown rendering.
- No server logic changes — the server already passes `detailed_message` through
  as-is in the FCM data payload.
- MCP server tests: 57/57 pass, ruff clean.
- Android tests: no changes needed. Existing JVM tests cover extractContent and
  mapToFields (pure functions); DetailActivity requires Android Context so cannot
  be unit-tested without Robolectric. Not added — would be a separate effort.

### Review fixes

- Added `LinkMovementMethod` to the detail TextView so markdown links are
  clickable. Removed `textIsSelectable` from XML (conflicts with
  LinkMovementMethod — the latter overrides the former's movement method).
- Moved Markwon instance to a companion `lazy` singleton to avoid rebuilding
  plugins on every DetailActivity launch. Added `appContext` to
  McpNotifApplication companion object.
- Added `lineSpacingExtra="4dp"` to the detail TextView for readability with
  rendered markdown blocks.
- Fixed pre-existing README test count drift (17 -> 20).

## Review Triage Log

- Links not clickable (no LinkMovementMethod) — high — patched. Links in
  markdown were styled but non-functional without LinkMovementMethod.
- textIsSelectable conflicts with LinkMovementMethod — high — patched. Removed
  textIsSelectable from XML; LinkMovementMethod now handles interaction.
- No lineSpacingExtra on detail TextView — low — patched. Added 4dp for
  readability with code blocks and tables.
- Markwon instance per onCreate — medium — patched. Moved to companion lazy
  singleton.
- README test count stale (17 vs 20) — low — patched. Corrected to 20.
- 3500-byte limit constrains markdown content — low — deferred. Pre-existing
  FCM constraint; not caused by this change.
- No Robolectric test for markdown rendering — medium — deferred. Requires
  adding Robolectric dependency and infrastructure; separate effort.
