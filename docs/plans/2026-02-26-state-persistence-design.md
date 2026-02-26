# State Persistence: Build-time Embedding + Export/Import

**Date:** 2026-02-26
**Status:** Approved

## Problem

The TeleShelf reader stores all user state (read posts, starred posts, theme, active view) in browser `localStorage`. This state:

- Is lost when switching browsers or clearing browser data
- Cannot be backed up or transferred between machines
- Has no file-based representation for version control or manual management
- `readPosts` array grows unbounded over time

## Solution

Hybrid persistence: keep `localStorage` for fast runtime reads/writes, add file-based state via build-time embedding and Export/Import buttons.

## State File Format

`reader/state.json` (gitignored — personal data):

```json
{
  "version": 1,
  "exportedAt": "2026-02-26T12:00:00Z",
  "channels": {
    "channel-slug": {
      "readPosts": [42, 43, 44],
      "lastSyncMaxId": 100
    }
  },
  "starred": {
    "channel-slug:42": true,
    "channel-slug:55": true
  },
  "preferences": {
    "theme": "dark",
    "activeView": "latest"
  }
}
```

`version` field allows future schema migration.

## Data Flow

```
[Browser localStorage] ---(Export btn)---> reader/state.json
        |                                        |
        |  (runtime: read/write)          (build time: read)
        |                                        |
        v                                        v
   [reader JS state]  <---(on load)---  [<script id="saved-state"> in HTML]
                       <---(Import btn)---  [any state.json file]
```

### On page load

1. Parse embedded state from `<script id="saved-state">` (if present)
2. Parse localStorage state (per channel keys)
3. Merge: union `readPosts`, max `lastSyncMaxId`, union starred, localStorage wins for preferences
4. Write merged result back to localStorage

### Runtime

All reads/writes go to localStorage. No change to current behavior.

### Export

User clicks Export button in toolbar. JS serializes full state (all channels + starred + preferences) into a JSON blob and triggers browser file download as `state.json`.

### Import

User clicks Import button in toolbar. File picker opens. JS reads the selected JSON file, validates format, merges into localStorage using the same union strategy as page-load merge. No rebuild needed.

### Build time

`build_reader.py` reads `reader/state.json` if it exists and embeds it as `<script id="saved-state" type="application/json">` in the HTML. If the file doesn't exist, the script block is omitted (backward compatible).

## Merge Strategy

For each channel:
- `readPosts`: set union of both sources (deduplicated)
- `lastSyncMaxId`: max of both values

For starred:
- Set union of both sources

For preferences (theme, activeView):
- localStorage wins (more recent)

## UI Changes

Toolbar additions (next to theme toggle):
- **Export button** — downloads `state.json`
- **Import button** — opens file picker, merges selected file into state

No other UI changes.

## Build Changes

`build_reader.py`:
- Read `reader/state.json` if it exists
- Pass content to template as `saved_state_json` variable
- Template renders `<script id="saved-state" type="application/json">{{ saved_state_json }}</script>` when present

## Gitignore

`reader/state.json` added to `.gitignore` — it contains personal reading state.

## Scope Exclusions

- No auto-save (would require a server)
- No `readPosts` pruning (separate concern, can be addressed later)
- No cross-device sync
