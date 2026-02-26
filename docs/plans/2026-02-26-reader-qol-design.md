# Reader QoL Improvements

**Date:** 2026-02-26
**Status:** Approved

## Problem

The TeleShelf reader lacks keyboard navigation, has a broken toolbar on mobile, shows no feedback for empty filter results, displays blank rows for text-less posts, and limits search to the first 300 characters of each post.

## Changes

### 1. Keyboard Navigation

Hotkeys (active when focus is not in `<input>` / `<select>`):

| Key | Action |
|-----|--------|
| `j` | Move to next post |
| `k` | Move to previous post |
| `n` | Jump to next unread post |
| `p` | Jump to previous unread post |
| `Enter` / `o` | Expand/collapse selected post (marks as read) |
| `Esc` | Collapse currently open post |
| `s` | Toggle star on selected post |
| `/` | Focus search input |

Implementation:
- Track `currentIndex` within the visible (non-hidden) rows of the active feed-list
- Add `.focused` CSS class to the current row (left border accent highlight)
- `keydown` listener on `document`, ignored when focus is in `<input>` or `<select>`
- Scroll focused row into view (`scrollIntoView({ block: "nearest" })`)
- Reset `currentIndex` on view switch

### 2. Mobile Toolbar (max-width: 767px)

Hide non-essential elements via CSS `display: none`:
- Tag dropdown (`#tag-select`)
- Starred button (`#btn-starred`)
- Counter (`#counter`)
- Export button (`#btn-export`)
- Import button (`#btn-import`)

Keep visible: hamburger, search input, "Прочитать все", theme toggle.

Tags and starred are already accessible via the sidebar on mobile.

### 3. Empty States

When all rows in the active feed-list are hidden by filters, show a centered message:

- Search with no results: "Ничего не найдено"
- Tag filter with no results: "Нет постов с тегом «X»"
- Star filter with no results: "Нет избранных постов"
- Combination: generic "Ничего не найдено"

Implementation:
- Add `<div class="empty-state">` inside each feed-list, hidden by default
- After each filter application, check if all rows are hidden; if so, show the empty state with appropriate text
- Hide empty state when filter is cleared or results appear

### 4. Posts Without Text — Fallback Display

In the compact row, when a post has no text, show a fallback title based on media type:

- Image file → `[Фото]`
- Video file → `[Видео]`
- Other file → `[Файл: filename.ext]`
- No text, no media → `[Пустой пост]`

Implementation: modify `extract_title_preview()` in `build_reader.py` to accept `file_field` parameter and generate fallback when text is empty. The fallback is rendered in muted style to distinguish from real titles.

### 5. Remove Search Text Limit

Remove the `[:300]` truncation in `prepare_post()` so `data-search-text` contains the full post text. This increases HTML size slightly but enables full-text search.

## Scope Exclusions

- No virtual scrolling (performance optimization for large lists — separate concern)
- No "mark as unread" feature
- No search highlighting
- No multi-field search (by channel name, tag, date)
- No overflow menu on mobile (CSS hide is sufficient)
