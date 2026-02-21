# BazQux-Style Reader Redesign

## Goal

Redesign the TeleShelf reader (`reader/index.html`) to match the BazQux Reader aesthetic: compact list view, sidebar with channel list and unread counts, toolbar with search, dark theme by default.

## Architecture

Refactor `build_reader.py` to use Jinja2 templates. Extract CSS and JS into separate files under `scripts/static/` and `scripts/templates/`. The final output remains a single self-contained `reader/index.html` (CSS/JS inlined at build time).

### File Structure

```
scripts/
  build_reader.py          # Data loading + Jinja2 rendering
  templates/
    reader.html            # Main layout template
    macros.html            # Reusable macros (post row, expanded post, thread)
  static/
    reader.css             # All styles
    reader.js              # All JS logic
requirements.txt           # jinja2
```

## Layout

```
+------------------+------------------------------------------+
| SIDEBAR (220px)  |  TOOLBAR (search, tags, mark all read)   |
|                  +------------------------------------------+
| - Latest (all)   |  LIST VIEW                               |
| - Channel 1  30  |  ch-name | **title** - preview... | date |
| - Channel 2  125 |  ch-name | **title** - preview... | date |
|                  |  [expanded post with full text/media]     |
|                  |  ch-name | **title** - preview... | date |
+------------------+------------------------------------------+
```

- **Sidebar** (fixed, left, 220px): "Latest" (all channels combined) + per-channel entries with unread counts. Tags section below channels.
- **Toolbar** (fixed, top): search input, tag filter dropdown, "Mark all as read" button, theme toggle.
- **Main area**: compact list view. Each post is one row. Click expands inline (accordion, multiple can be open).

## Visual Design

### Dark theme (default)
- Background: `#1e1e1e`
- Sidebar: `#252526`
- Text: `#d4d4d4`, muted: `#888`
- Accent: `#e8a838` (orange, for active items and counts)
- Row hover: `#2a2d2e`
- Border: `#333`

### Light theme
- Background: `#faf8f5`
- Sidebar: `#f3f0eb`
- Text: `#2c2c2c`, muted: `#888`
- Accent: `#d48820`
- Row hover: `rgba(0,0,0,0.03)`

### List view row (~32px height)
- Left: channel color dot + channel name (truncated, gray)
- Center: **title** (bold, first ~60 chars of text) — preview (gray, rest of text, ellipsis)
- Right: compact date (e.g. `21 фев`)
- Unread rows: bolder text. Read rows: muted.

### Expanded post (on click)
- Opens below the row
- Full text, media (images/videos), tags as badges, threads
- Slightly different background to distinguish from list

### Sidebar
- "Latest" at top (all channels merged, sorted by date, total unread count)
- Each channel: name + unread count
- Active channel highlighted in accent color
- Tags section below channel list (collapsible)

## Features

### Kept from current reader
- Read tracking via IntersectionObserver + localStorage
- New post badges (posts added since last visit)
- Theme toggle (dark/light), persisted in localStorage
- Tag filtering in sidebar
- Thread display (inline, in expanded posts)
- Fully offline single HTML file
- Mobile responsive (hamburger menu for sidebar)

### Added (BazQux-style)
- **Search**: text input in toolbar, client-side filtering by post text
- **Sidebar channel list**: channels with unread counts (replaces dropdown)
- **"Latest" view**: all channels in one stream, sorted by date descending
- **Mark all as read**: button in toolbar
- **Compact list view**: rows instead of cards, accordion expand on click

### Removed
- Sidebar post list (replaced by list view in main area)
- Channel dropdown in header (replaced by sidebar)
- Post `#id` as heading (replaced by text preview)

## Decisions

- **Jinja2 templates** for cleaner separation of data/presentation
- **Dark theme default** to match BazQux aesthetic
- **Inline accordion** (multiple open) for expanded posts — simpler than single-open
- **Client-side search** — sufficient for the data volume, no server needed
- **Single HTML output** preserved — CSS/JS inlined at build time from separate source files
