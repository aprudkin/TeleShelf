# Channel Reader — Design Document

**Date:** 2026-02-20
**Status:** Approved

## Goal

Turn a downloaded Telegram channel into a local static website that works like a book reader with read-tracking and new-post markers after sync.

## Requirements

- Local-only, single user (no auth, no backend)
- Single channel at a time (iishenka-pro for v1)
- Read progress stored in browser localStorage
- New posts highlighted after re-generation following sync
- Static HTML file — works with `file://` protocol, zero dependencies

## Architecture

### Generation

- Python script `scripts/build_reader.py` accepts a channel slug
- Reads `downloads/<slug>/channel-full/all-messages.json` + `downloads/<slug>/threads/thread-*.json`
- Generates `downloads/<slug>/reader/index.html` (single file: HTML + CSS + JS inlined)
- Media references use relative paths to `../channel-main/` and `../threads-media/`
- Integrated into Taskfile as `task build-reader -- <slug>`

### Output

```
downloads/<slug>/reader/
  index.html          # self-contained (HTML + CSS + JS)
```

### Read Tracking (localStorage)

- Key: `reader-<channel_id>`
- Value: `{ readPosts: [12, 13, ...], lastSyncMaxId: 154 }`
- A post is marked as read when its top edge enters the viewport (IntersectionObserver)
- "Mark all as read" button available

### New Post Detection

- At generation time, `data-max-id="<max_post_id>"` is embedded in the HTML
- On page load, JS compares `lastSyncMaxId` from localStorage with the current `data-max-id`
- Posts with ID > `lastSyncMaxId` get a "NEW" badge
- Badge is removed when the post is scrolled into view
- `lastSyncMaxId` is updated to `data-max-id` once all new posts are viewed (or on "mark all read")

## UI / Layout

### Desktop (>= 768px)

```
+--------------------------------------------------+
|  ИИшенка Pro - Читалка                     [≡]  |
+----------------+---------------------------------+
|  Оглавление    |                                 |
|                |   Пост #9                       |
|  ✓ #9          |   16 мая 2025, 09:51            |
|  ✓ #11  🎥     |                                 |
|  ● #12  🖼     |   Текст поста...                |
|    #13  🖼     |                                 |
|    ...         |   ▶ Комментарии (193)           |
|                |   ─────────────────             |
|  ──────────    |   Пост #11                      |
|  2/139         |   16 мая 2025, 10:55            |
|  1 новый       |   [▶ Видео]                     |
|                |   Текст поста...                |
+----------------+---------------------------------+
```

### Sidebar (left, ~250px)

- Post list: `#ID` + date + media icon (🖼/🎥)
- Read posts: checkmark, muted color
- New posts: orange "NEW" badge
- Current post (in viewport): highlighted
- Click scrolls to post
- Counter at bottom: "Прочитано X из Y, Z новых"
- "Mark all as read" button

### Mobile (< 768px)

- Sidebar hidden, toggled via hamburger button [≡]
- Full-width content area

### Content Area (right)

- Posts sorted by ID ascending (oldest first, like a book)
- Each post: date, media (lazy-loaded `<img>` / `<video controls>`), text
- Threads: collapsible `<details>` block under the post showing thread messages
- Separator between posts

### Styling

- Light warm color scheme (paper-like for reading)
- System font stack for readability
- Max content width ~700px for comfortable reading

## Data Flow

### Message Schema (from all-messages.json)

```json
{
  "id": 154,
  "type": "message",
  "file": "5235447490834798210.jpg",
  "date": 1771409819,
  "text": "..."
}
```

### Thread Schema (from threads/thread-{POST_ID}.json)

```json
{
  "id": 2558997551,
  "messages": [
    { "id": 4497, "type": "message", "file": "", "date": 1771409887, "text": "..." }
  ]
}
```

### Media Path Resolution

- Post media: `../channel-main/{channel_id}_{post_id}_{file_field}` — but actual files use pattern `{CHANNEL_ID}_{POST_ID}_{FILE_ID}.{ext}`, so the script must match by `{channel_id}_{post_id}_` prefix in the directory
- Thread media: not displayed in v1 (text-only thread comments)

## Workflow

```bash
# 1. Sync new messages + media
task sync -- iishenka-pro

# 2. Regenerate reader
task build-reader -- iishenka-pro

# 3. Open in browser
open downloads/iishenka-pro/reader/index.html
```

### What Happens on Rebuild After Sync

1. Script generates new `index.html` with all posts (including new ones)
2. `data-max-id` updates to new maximum
3. On open, JS detects `data-max-id` > `lastSyncMaxId` in localStorage
4. New posts get "NEW" badge
5. Scrolling to them marks as read and eventually updates `lastSyncMaxId`

## Scope Limitations (v1)

- Single channel only
- No search
- No dark theme
- Thread media not displayed (text comments only)
- No read-progress export/import
- No multi-device sync

## Future Enhancements (not in v1)

- Multi-channel support with landing page
- Full-text search (client-side)
- Dark theme toggle
- Thread media display
- Bookmark/highlight specific posts
- Export/import read progress
