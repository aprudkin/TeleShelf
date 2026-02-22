# Channel Reader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate a static HTML reader from downloaded Telegram channel data with read-tracking and new-post markers.

**Architecture:** Python script reads `all-messages.json` + thread JSONs, generates a single self-contained `index.html` with inlined CSS and JS. Read progress stored in browser localStorage. New posts detected by comparing embedded `data-max-id` with saved `lastSyncMaxId`.

**Tech Stack:** Python 3 (stdlib only), HTML5, CSS3, vanilla JS

---

## Data Reference

Before implementing, understand these exact data shapes:

**channel.json:**
```json
{ "channel_id": "2564209658", "discussion_group_id": "2558997551", "name": "IIshenka Pro" }
```

**all-messages.json:** `{ "id": 2564209658, "messages": [ { "id": 154, "type": "message", "file": "5235447490834798210.jpg", "date": 1771409819, "text": "..." }, ... ] }` — sorted desc by ID. `file` is `""` when no media. `text` is always present.

**threads/thread-{POST_ID}.json:** `{ "id": 2558997551, "messages": [ { "id": 4443, "type": "message", "file": "", "date": 1771272069, "text": "..." } ] }` — `text` field may be **absent** (not empty) on media-only thread messages. Also `thread-{POST_ID}-channel.json` exists as fallback variant.

**Media files in channel-main/:** Named `{CHANNEL_ID}_{POST_ID}_{FILE_FIELD}` e.g. `2564209658_154_5235447490834798210.jpg`. The `{FILE_FIELD}` part matches the message's `file` field exactly. So the full path is: `../channel-main/{channel_id}_{post_id}_{file_field}`.

**Special files to skip in threads/:** `all-threads-media.json` and `channel-threads-media.json` are aggregate files, not individual threads.

---

### Task 1: Python Script — Data Loading

**Files:**
- Create: `scripts/build_reader.py`

**Step 1: Create script with argument parsing and data loading**

```python
#!/usr/bin/env python3
"""Generate a static HTML reader for a downloaded Telegram channel."""

import json
import os
import sys
import glob
from datetime import datetime, timezone, timedelta

def main():
    if len(sys.argv) != 2:
        print("Usage: build_reader.py <slug>", file=sys.stderr)
        sys.exit(1)

    slug = sys.argv[1]
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads", slug)

    # Load channel config
    config_path = os.path.join(base_dir, "channel.json")
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        config = json.load(f)

    channel_id = config["channel_id"]
    channel_name = config.get("name", slug)

    # Load messages (sorted desc in file, we need asc)
    messages_path = os.path.join(base_dir, "channel-full", "all-messages.json")
    with open(messages_path) as f:
        data = json.load(f)
    messages = sorted(data.get("messages", []), key=lambda m: m["id"])

    if not messages:
        print("No messages found.", file=sys.stderr)
        sys.exit(1)

    max_id = max(m["id"] for m in messages)

    # Load threads: prefer thread-{id}.json, fallback to thread-{id}-channel.json
    threads_dir = os.path.join(base_dir, "threads")
    threads = {}  # post_id -> list of thread messages
    if os.path.isdir(threads_dir):
        for msg in messages:
            post_id = msg["id"]
            thread_path = os.path.join(threads_dir, f"thread-{post_id}.json")
            if not os.path.exists(thread_path):
                thread_path = os.path.join(threads_dir, f"thread-{post_id}-channel.json")
            if os.path.exists(thread_path):
                with open(thread_path) as f:
                    thread_data = json.load(f)
                thread_msgs = thread_data.get("messages", [])
                if thread_msgs:
                    threads[post_id] = sorted(thread_msgs, key=lambda m: m["id"])

    print(f"Loaded {len(messages)} posts, {len(threads)} threads")
    print(f"Max post ID: {max_id}")

    # Generate HTML
    html = generate_html(channel_name, channel_id, messages, threads, max_id)

    # Write output
    output_dir = os.path.join(base_dir, "reader")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w") as f:
        f.write(html)

    print(f"Generated: {output_path}")
```

**Step 2: Run to verify it loads data (will fail on missing generate_html)**

Run: `cd /Users/alexeyprudkin/dev/scrap-tg && python3 scripts/build_reader.py iishenka-pro`
Expected: Error about `generate_html` not defined — confirms data loading works up to that point.

**Step 3: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: add build_reader.py with data loading"
```

---

### Task 2: HTML Generation — Post Content

**Files:**
- Modify: `scripts/build_reader.py`

**Step 1: Add helper functions for date formatting and media resolution**

```python
def format_date(unix_ts):
    """Format Unix timestamp to Russian-locale date string."""
    # Moscow timezone (UTC+3) — channel content is Russian
    dt = datetime.fromtimestamp(unix_ts, tz=timezone(timedelta(hours=3)))
    months = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    return f"{dt.day} {months[dt.month]} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"

def get_media_html(channel_id, post_id, file_field):
    """Return HTML for a media file, or empty string if no media."""
    if not file_field:
        return ""
    path = f"../channel-main/{channel_id}_{post_id}_{file_field}"
    ext = file_field.rsplit(".", 1)[-1].lower() if "." in file_field else ""
    if ext in ("mp4", "mov", "webm"):
        return f'<div class="media"><video controls preload="none" src="{path}"></video></div>'
    elif ext in ("jpg", "jpeg", "png", "gif", "webp"):
        return f'<div class="media"><img loading="lazy" src="{path}" alt=""></div>'
    else:
        return f'<div class="media"><a href="{path}" download>{file_field}</a></div>'

def escape_html(text):
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def format_text(text):
    """Convert plain text to HTML with paragraph breaks."""
    if not text:
        return ""
    paragraphs = escape_html(text).split("\n\n")
    result = []
    for p in paragraphs:
        lines = p.split("\n")
        result.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(result)

def media_icon(file_field):
    """Return a media type icon for the sidebar."""
    if not file_field:
        return ""
    ext = file_field.rsplit(".", 1)[-1].lower() if "." in file_field else ""
    if ext in ("mp4", "mov", "webm"):
        return '<span class="icon icon-video" title="Видео"></span>'
    return '<span class="icon icon-image" title="Изображение"></span>'
```

**Step 2: Add the generate_html function — post content section**

```python
def generate_html(channel_name, channel_id, messages, threads, max_id):
    """Generate the complete HTML page."""
    total = len(messages)

    # Build sidebar items and post content
    sidebar_items = []
    post_sections = []

    for msg in messages:
        post_id = msg["id"]
        file_field = msg.get("file", "")
        text = msg.get("text", "")
        date_str = format_date(msg["date"])

        # Sidebar item
        sidebar_items.append(
            f'<li class="sidebar-item" data-post-id="{post_id}">'
            f'<span class="sidebar-check"></span>'
            f'<a href="#post-{post_id}">#{post_id}</a> '
            f'<span class="sidebar-date">{date_str}</span>'
            f'{media_icon(file_field)}'
            f'<span class="badge-new">NEW</span>'
            f'</li>'
        )

        # Post content
        media_html = get_media_html(channel_id, post_id, file_field)
        text_html = format_text(text)

        # Thread
        thread_html = ""
        thread_msgs = threads.get(post_id, [])
        if thread_msgs:
            thread_comments = []
            for tm in thread_msgs:
                tm_text = tm.get("text", "")
                tm_date = format_date(tm["date"])
                tm_text_html = format_text(tm_text) if tm_text else '<p class="no-text"><em>медиа</em></p>'
                thread_comments.append(
                    f'<div class="thread-msg">'
                    f'<span class="thread-date">{tm_date}</span>'
                    f'{tm_text_html}'
                    f'</div>'
                )
            thread_html = (
                f'<details class="thread">'
                f'<summary>Комментарии ({len(thread_msgs)})</summary>'
                f'{"".join(thread_comments)}'
                f'</details>'
            )

        post_sections.append(
            f'<article class="post" id="post-{post_id}" data-post-id="{post_id}">'
            f'<h2>Пост #{post_id}</h2>'
            f'<time>{date_str}</time>'
            f'{media_html}'
            f'<div class="post-text">{text_html}</div>'
            f'{thread_html}'
            f'</article>'
        )

    # Assemble full HTML — CSS and JS added in next tasks
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape_html(channel_name)} — Читалка</title>
<style>
{CSS_CONTENT}
</style>
</head>
<body data-max-id="{max_id}" data-channel-id="{channel_id}" data-total-posts="{total}">

<header>
  <button id="sidebar-toggle" aria-label="Меню">&#9776;</button>
  <h1>{escape_html(channel_name)} — Читалка</h1>
</header>

<nav id="sidebar">
  <div class="sidebar-header">Оглавление</div>
  <ul id="sidebar-list">
    {"".join(sidebar_items)}
  </ul>
  <div class="sidebar-footer">
    <div id="read-counter">Прочитано: 0 из {total}</div>
    <div id="new-counter"></div>
    <button id="mark-all-read">Отметить все прочитанным</button>
  </div>
</nav>

<main id="content">
  {"".join(post_sections)}
</main>

<script>
{JS_CONTENT}
</script>
</body>
</html>'''
```

**Step 3: Add placeholder CSS_CONTENT and JS_CONTENT constants (will be filled in next tasks)**

```python
CSS_CONTENT = "/* placeholder */"
JS_CONTENT = "/* placeholder */"
```

**Step 4: Run to verify HTML generation works**

Run: `cd /Users/alexeyprudkin/dev/scrap-tg && python3 scripts/build_reader.py iishenka-pro`
Expected: `Generated: downloads/iishenka-pro/reader/index.html` — open it in browser, see raw unstyled posts.

**Step 5: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: add HTML generation for posts, threads, sidebar"
```

---

### Task 3: CSS Styling

**Files:**
- Modify: `scripts/build_reader.py` — replace `CSS_CONTENT` placeholder

**Step 1: Replace CSS_CONTENT with the full stylesheet**

Replace the `CSS_CONTENT = "/* placeholder */"` line with a multi-line string containing:

```python
CSS_CONTENT = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #faf8f5;
  --sidebar-bg: #f3f0eb;
  --text: #2c2c2c;
  --text-muted: #888;
  --border: #e0dbd4;
  --accent: #5b7a3a;
  --new-badge: #e67e22;
  --highlight: #f0ead6;
  --sidebar-w: 260px;
  --content-max: 700px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}

header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--sidebar-bg);
  border-bottom: 1px solid var(--border);
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

header h1 {
  font-size: 1.1rem;
  font-weight: 600;
}

#sidebar-toggle {
  display: none;
  background: none;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 1.3rem;
  padding: 4px 8px;
  cursor: pointer;
}

/* Sidebar */
#sidebar {
  position: fixed;
  top: 49px;
  left: 0;
  bottom: 0;
  width: var(--sidebar-w);
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 90;
}

.sidebar-header {
  padding: 12px 16px 8px;
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

#sidebar-list {
  list-style: none;
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.sidebar-item {
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.sidebar-item:hover { background: var(--highlight); }
.sidebar-item.active { background: var(--highlight); font-weight: 600; }
.sidebar-item.read { color: var(--text-muted); }

.sidebar-item a {
  color: inherit;
  text-decoration: none;
}

.sidebar-check {
  width: 16px;
  text-align: center;
  flex-shrink: 0;
}

.sidebar-item.read .sidebar-check::before { content: "\\2713"; color: var(--accent); }

.sidebar-date {
  flex: 1;
  margin-left: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.icon { margin-left: 2px; }
.icon-image::before { content: "\\1f5bc"; font-size: 0.75rem; }
.icon-video::before { content: "\\1f3a5"; font-size: 0.75rem; }

.badge-new {
  display: none;
  background: var(--new-badge);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: auto;
  flex-shrink: 0;
}

.sidebar-item.new .badge-new { display: inline-block; }

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  font-size: 0.8rem;
  color: var(--text-muted);
}

#new-counter { margin-top: 4px; color: var(--new-badge); font-weight: 600; }
#new-counter:empty { display: none; }

#mark-all-read {
  margin-top: 8px;
  width: 100%;
  padding: 6px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}

#mark-all-read:hover { opacity: 0.9; }

/* Content */
main {
  margin-left: var(--sidebar-w);
  padding: 24px 20px 80px;
}

.post {
  max-width: var(--content-max);
  margin: 0 auto 40px;
  padding-bottom: 40px;
  border-bottom: 1px solid var(--border);
}

.post:last-child { border-bottom: none; }

.post h2 {
  font-size: 1.15rem;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.post h2 .post-new-badge {
  display: none;
  background: var(--new-badge);
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 3px;
}

.post.new-post h2 .post-new-badge { display: inline-block; }

.post time {
  display: block;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.media { margin: 16px 0; }
.media img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
}
.media video {
  max-width: 100%;
  border-radius: 6px;
}

.post-text p { margin-bottom: 12px; }
.post-text p:last-child { margin-bottom: 0; }

/* Thread */
.thread {
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: 6px;
}

.thread summary {
  padding: 10px 14px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--accent);
  user-select: none;
}

.thread summary:hover { background: var(--highlight); }

.thread-msg {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}

.thread-date {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.thread-msg p { font-size: 0.9rem; margin-bottom: 8px; }
.thread-msg p:last-child { margin-bottom: 0; }

.no-text { color: var(--text-muted); }

/* Mobile */
@media (max-width: 768px) {
  #sidebar-toggle { display: block; }

  #sidebar {
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }

  #sidebar.open { transform: translateX(0); }

  main { margin-left: 0; }
}
"""
```

**Step 2: Also add the `<span class="post-new-badge">NEW</span>` inside the h2 in generate_html**

In the post_sections building, change the h2 line:
```python
f'<h2>Пост #{post_id} <span class="post-new-badge">NEW</span></h2>'
```

**Step 3: Run and open in browser to verify styling**

Run: `cd /Users/alexeyprudkin/dev/scrap-tg && python3 scripts/build_reader.py iishenka-pro && open downloads/iishenka-pro/reader/index.html`
Expected: Styled page with sidebar on the left, posts on the right, warm paper-like colors.

**Step 4: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: add CSS styling — sidebar, posts, threads, mobile"
```

---

### Task 4: JavaScript — Read Tracking & New Post Detection

**Files:**
- Modify: `scripts/build_reader.py` — replace `JS_CONTENT` placeholder

**Step 1: Replace JS_CONTENT with the full JavaScript**

```python
JS_CONTENT = """
(function() {
  'use strict';

  const body = document.body;
  const channelId = body.dataset.channelId;
  const maxId = parseInt(body.dataset.maxId, 10);
  const totalPosts = parseInt(body.dataset.totalPosts, 10);
  const STORAGE_KEY = 'reader-' + channelId;

  // State
  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const s = JSON.parse(raw);
        return {
          readPosts: new Set(s.readPosts || []),
          lastSyncMaxId: s.lastSyncMaxId || 0
        };
      }
    } catch(e) {}
    return { readPosts: new Set(), lastSyncMaxId: 0 };
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      readPosts: Array.from(state.readPosts),
      lastSyncMaxId: state.lastSyncMaxId
    }));
  }

  const state = loadState();

  // Determine new posts (ID > lastSyncMaxId)
  const newPostIds = new Set();
  if (state.lastSyncMaxId > 0 && state.lastSyncMaxId < maxId) {
    document.querySelectorAll('.post').forEach(function(el) {
      const pid = parseInt(el.dataset.postId, 10);
      if (pid > state.lastSyncMaxId) {
        newPostIds.add(pid);
      }
    });
  }

  // Apply initial state to DOM
  function updateDOM() {
    let readCount = 0;
    let newCount = 0;

    document.querySelectorAll('.sidebar-item').forEach(function(li) {
      const pid = parseInt(li.dataset.postId, 10);
      li.classList.toggle('read', state.readPosts.has(pid));
      li.classList.toggle('new', newPostIds.has(pid) && !state.readPosts.has(pid));
    });

    document.querySelectorAll('.post').forEach(function(el) {
      const pid = parseInt(el.dataset.postId, 10);
      const isNew = newPostIds.has(pid) && !state.readPosts.has(pid);
      el.classList.toggle('new-post', isNew);
      if (isNew) newCount++;
      if (state.readPosts.has(pid)) readCount++;
    });

    document.getElementById('read-counter').textContent =
      'Прочитано: ' + readCount + ' из ' + totalPosts;

    const newEl = document.getElementById('new-counter');
    newEl.textContent = newCount > 0 ? ('Новых: ' + newCount) : '';

    // Update lastSyncMaxId if no new posts remain
    if (newCount === 0 && maxId > state.lastSyncMaxId) {
      state.lastSyncMaxId = maxId;
      saveState();
    }
  }

  function markRead(postId) {
    if (state.readPosts.has(postId)) return;
    state.readPosts.add(postId);
    saveState();
    updateDOM();
  }

  // IntersectionObserver — mark post as read when visible
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        const pid = parseInt(entry.target.dataset.postId, 10);
        markRead(pid);
      }
    });
  }, { threshold: 0.3 });

  document.querySelectorAll('.post').forEach(function(el) {
    observer.observe(el);
  });

  // Track current post in viewport for sidebar highlight
  const currentObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      const pid = entry.target.dataset.postId;
      const sidebarItem = document.querySelector('.sidebar-item[data-post-id=\"' + pid + '\"]');
      if (sidebarItem) {
        sidebarItem.classList.toggle('active', entry.isIntersecting);
        if (entry.isIntersecting) {
          sidebarItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.post').forEach(function(el) {
    currentObserver.observe(el);
  });

  // Sidebar click → scroll to post
  document.getElementById('sidebar-list').addEventListener('click', function(e) {
    const li = e.target.closest('.sidebar-item');
    if (!li) return;
    e.preventDefault();
    const pid = li.dataset.postId;
    const post = document.getElementById('post-' + pid);
    if (post) {
      post.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // Close mobile sidebar
    document.getElementById('sidebar').classList.remove('open');
  });

  // Mark all as read
  document.getElementById('mark-all-read').addEventListener('click', function() {
    document.querySelectorAll('.post').forEach(function(el) {
      state.readPosts.add(parseInt(el.dataset.postId, 10));
    });
    state.lastSyncMaxId = maxId;
    newPostIds.clear();
    saveState();
    updateDOM();
  });

  // Mobile sidebar toggle
  document.getElementById('sidebar-toggle').addEventListener('click', function() {
    document.getElementById('sidebar').classList.toggle('open');
  });

  // First load: if lastSyncMaxId is 0 (first visit), set it to maxId so nothing is "new"
  if (state.lastSyncMaxId === 0) {
    state.lastSyncMaxId = maxId;
    saveState();
  }

  updateDOM();
})();
"""
```

**Step 2: Run and test in browser**

Run: `cd /Users/alexeyprudkin/dev/scrap-tg && python3 scripts/build_reader.py iishenka-pro && open downloads/iishenka-pro/reader/index.html`
Expected:
- Posts appear with styling
- Scrolling marks posts as read (checkmark in sidebar)
- Counter updates: "Прочитано: X из 139"
- First visit: no "NEW" badges (lastSyncMaxId set to maxId)
- Sidebar click scrolls to post

**Step 3: Verify new-post detection manually**

Open browser console, run:
```js
localStorage.setItem('reader-2564209658', JSON.stringify({readPosts: [], lastSyncMaxId: 140}));
location.reload();
```
Expected: Posts 141+ show "NEW" badge in sidebar and content.

**Step 4: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: add JS — read tracking, new post detection, sidebar navigation"
```

---

### Task 5: Taskfile Integration

**Files:**
- Modify: `Taskfile.yml`

**Step 1: Add build-reader task to Taskfile.yml**

Append after the `sync` task:

```yaml
  build-reader:
    desc: Generate static HTML reader for a channel
    summary: |
      Usage: task build-reader -- <slug>

      Generates downloads/<slug>/reader/index.html from channel data.
      Open the HTML file in a browser to read the channel like a book.

      Arguments:
        slug    Channel slug (directory name under downloads/)

      Example:
        task build-reader -- iishenka-pro
    preconditions:
      - sh: '[ -n "{{.CLI_ARGS}}" ]'
        msg: "Error: slug is required. Usage: task build-reader -- <slug>"
      - sh: '[ -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel.json" ]'
        msg: "Error: channel.json not found. Run 'task add-channel' first."
      - sh: '[ -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel-full/all-messages.json" ]'
        msg: "Error: all-messages.json not found. Run 'task sync' first."
    silent: true
    cmd: |
      python3 "{{.ROOT_DIR}}/scripts/build_reader.py" "{{.CLI_ARGS}}"
      echo ""
      echo "Reader ready! Open:"
      echo "  open {{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/reader/index.html"
```

**Step 2: Run via task**

Run: `cd /Users/alexeyprudkin/dev/scrap-tg && task build-reader -- iishenka-pro`
Expected: Success message with path to generated file.

**Step 3: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add build-reader task to Taskfile"
```

---

### Task 6: End-to-End Verification

**Step 1: Clean and regenerate**

```bash
rm -rf downloads/iishenka-pro/reader/
task build-reader -- iishenka-pro
```

**Step 2: Open and verify checklist**

Open `downloads/iishenka-pro/reader/index.html` in browser. Verify:

- [ ] Page loads with warm paper-like styling
- [ ] Sidebar shows all 139 posts with IDs and dates
- [ ] Scrolling through posts marks them as read (checkmarks appear)
- [ ] "Прочитано: X из 139" counter updates live
- [ ] First visit: no "NEW" badges
- [ ] Clicking sidebar item scrolls to post
- [ ] Images load (lazy-loaded, from `../channel-main/`)
- [ ] Video plays (post #11 welcome.mp4)
- [ ] Thread comments expandable under posts with threads
- [ ] Mobile: resize to < 768px, hamburger menu shows, sidebar slides in/out
- [ ] Simulate new posts: set lastSyncMaxId to 140 in console, reload → posts 141+ show "NEW"

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: channel reader v1 — static HTML with read tracking"
```

---

## Summary of Files Changed

| File | Action | Description |
|------|--------|-------------|
| `scripts/build_reader.py` | Create | Python generator: JSON → HTML reader |
| `Taskfile.yml` | Modify | Add `build-reader` task |
| `downloads/<slug>/reader/index.html` | Generated | Output (not committed) |
