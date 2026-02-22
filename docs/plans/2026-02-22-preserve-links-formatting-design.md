# Design: Preserve Links & Formatting in Reader

**Date:** 2026-02-22
**Status:** Approved

## Problem

`tdl chat export` (without `--raw`) strips all Telegram entity metadata. Links embedded as `text_link` (e.g., display text "Персонал Корп у" pointing to sereja.tech), blockquotes, and formatting are permanently lost. The reader's `format_text()` only regex-matches bare URLs in plain text.

Example: post https://t.me/ris_ai/576 loses two links:
- `sereja.tech/blog/personal-corporation-event-driven-agents/`
- `sereja.tech/blog/github-projects-ai-agent-memory`

## Approach

Use `tdl --raw` to get MTProto entity data. Extract identifiable entity types (text_link, blockquote, custom_emoji) and apply them during HTML rendering. Accept that bold/italic/code/strikethrough cannot be distinguished in tdl's JSON serialization (all serialize as bare `{Offset, Length}`).

## Data Format Change

Messages in `all-messages.json` gain an optional `entities` array:

```json
{
  "id": 576,
  "type": "message",
  "text": "...",
  "date": 1770834070,
  "file": "5217773498548293804.jpg",
  "entities": [
    {"type": "text_link", "offset": 62, "length": 15, "url": "https://sereja.tech/blog/..."},
    {"type": "blockquote", "offset": 1087, "length": 110},
    {"type": "custom_emoji", "offset": 0, "length": 2},
    {"type": "unknown", "offset": 103, "length": 28}
  ]
}
```

- Offsets/lengths converted from UTF-16 to Python string indices at extraction time
- Entity type detected by presence of unique JSON fields:
  - `URL` field → `text_link`
  - `Flags` + `Collapsed` fields → `blockquote`
  - `DocumentID` field → `custom_emoji`
  - Only `Offset` + `Length` → heuristic detection or `unknown`
- Backwards compatible: messages without `entities` use bare-URL regex fallback

## Entity Type Heuristics

For bare `{Offset, Length}` entities (no distinguishing fields), infer from text content:

| Text Pattern | Inferred Type | Rendering |
|---|---|---|
| `#\w+` | hashtag | no special treatment |
| `@\w+` | mention | link to `t.me/<username>` |
| `https?://...` | url | clickable `<a>` tag |
| Everything else | unknown | no formatting applied |

Bold/italic/code/strikethrough stay unstyled — acceptable tradeoff since links and blockquotes are the critical losses.

## Rendering Changes

Rewrite `format_text(text, entities=None)`:
- If entities provided: apply entity-based HTML generation (links as `<a>`, blockquotes as `<blockquote>`)
- If no entities: fall back to current bare-URL regex (backwards compatible)
- Entity application: sort by offset, handle nesting, HTML-escape non-entity text segments

## Sync Pipeline Change

Current: `tdl chat export → merge → download media`
New: `tdl chat export --raw → extract entities → merge (with entities) → download media`

Entity extraction is a Python function called during the merge step in Taskfile.yml.

## Re-export Task

New `task re-export -- <slug>` and `task re-export-all`:
1. Export ALL messages from channel with `--raw`
2. Extract entities from raw data
3. Merge entities into existing `all-messages.json` by message ID
4. Rebuild reader

## Thread Support

Same entity extraction applies to thread exports (`thread-*.json`). Thread messages use the same raw format when exported with `--raw`.

## UTF-16 Handling

Telegram entities use UTF-16 code unit offsets. Emoji (surrogate pairs) take 2 UTF-16 units but 1 Python character. Conversion happens at extraction time — stored offsets are Python string indices.

## What This Does NOT Fix

- Bold, italic, underline, strikethrough, code, spoiler formatting (entity types indistinguishable in tdl JSON)
- Custom emoji rendering (stored but not displayed differently from regular emoji)
- Could be addressed later by switching to Telethon for export
