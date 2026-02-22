# BazQux-Style Reader Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign TeleShelf reader to BazQux-style: compact list view, sidebar channel list with unread counts, toolbar with search, dark theme default, Jinja2 templates.

**Architecture:** Extract CSS/JS/HTML into separate source files (`scripts/static/`, `scripts/templates/`). Refactor `build_reader.py` to load data and render via Jinja2. Output remains single self-contained `reader/index.html` with CSS/JS inlined at build time.

**Tech Stack:** Python 3, Jinja2, vanilla JS, CSS custom properties

---

### Task 1: Setup — Jinja2 dependency and directory structure

**Files:**
- Create: `requirements.txt`
- Create: `scripts/templates/` (directory)
- Create: `scripts/static/` (directory)

**Step 1: Create requirements.txt**

```
jinja2>=3.1
```

**Step 2: Install dependency**

Run: `pip3 install -r requirements.txt`

**Step 3: Create directories**

Run: `mkdir -p scripts/templates scripts/static`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add jinja2 dependency and template directories"
```

---

### Task 2: CSS — BazQux-style theme

**Files:**
- Create: `scripts/static/reader.css`

**Step 1: Create the CSS file**

Create `scripts/static/reader.css` with the complete BazQux-inspired styles. Key design notes:

- Dark theme by default (`:root` has dark colors, `body.light` overrides)
- CSS variables for theming
- `--sidebar-w: 220px` for sidebar
- No `--content-max` (list view is full width)
- Row height ~34px for list items
- Accent color `#e8a838` (BazQux orange)
- Font: system sans-serif, 13px base

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #1e1e1e;
  --bg-sidebar: #252526;
  --bg-toolbar: #2d2d30;
  --bg-row-hover: #2a2d2e;
  --bg-expanded: #252528;
  --text: #d4d4d4;
  --text-muted: #888;
  --text-title: #e0e0e0;
  --accent: #e8a838;
  --accent-light: #3a3020;
  --border: #333;
  --new-badge: #e8a838;
  --sidebar-w: 220px;
  --toolbar-h: 42px;
  --row-h: 34px;
}

body.light {
  --bg: #faf8f5;
  --bg-sidebar: #f3f0eb;
  --bg-toolbar: #eae6e0;
  --bg-row-hover: rgba(0,0,0,0.03);
  --bg-expanded: #f0ede8;
  --text: #2c2c2c;
  --text-muted: #888;
  --text-title: #1a1a1a;
  --accent: #d48820;
  --accent-light: #f5eacc;
  --border: #ddd;
  --new-badge: #d48820;
}

html { font-size: 13px; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  overflow: hidden;
  height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Toolbar ── */
.toolbar {
  position: fixed;
  top: 0; left: var(--sidebar-w); right: 0;
  height: var(--toolbar-h);
  background: var(--bg-toolbar);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 10px;
  z-index: 100;
}
.toolbar-search {
  flex: 0 0 220px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 3px;
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
}
.toolbar-search::placeholder { color: var(--text-muted); }
.toolbar-search:focus { outline: 1px solid var(--accent); border-color: var(--accent); }
.toolbar-tag-select {
  height: 26px;
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 3px;
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
  max-width: 180px;
}
.toolbar-spacer { flex: 1; }
.toolbar-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text-muted);
  font-size: 12px;
  padding: 3px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.toolbar-btn:hover { color: var(--text); border-color: var(--text-muted); }
.toolbar-counter {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}
.theme-toggle {
  background: none; border: none; cursor: pointer;
  font-size: 16px; padding: 2px 4px;
  color: var(--text-muted);
  line-height: 1;
}
.hamburger {
  display: none; background: none; border: none; cursor: pointer;
  font-size: 20px; padding: 2px 6px; color: var(--text);
}

/* ── Sidebar ── */
.sidebar {
  position: fixed;
  top: 0; left: 0; bottom: 0;
  width: var(--sidebar-w);
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  z-index: 110;
  overflow: hidden;
}
.sidebar-header {
  padding: 10px 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--accent);
  border-bottom: 1px solid var(--border);
}
.sidebar-channels {
  flex: 0 0 auto;
  overflow-y: auto;
  border-bottom: 1px solid var(--border);
}
.channel-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
  transition: background 0.1s;
}
.channel-item:hover { background: var(--bg-row-hover); }
.channel-item.active { color: var(--accent); font-weight: 600; }
.channel-dot {
  width: 8px; height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}
.channel-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.channel-count {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}
.channel-item.active .channel-count { color: var(--accent); }

/* ── Sidebar tags ── */
.sidebar-tags {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}
.sidebar-tags-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.tag-list { display: flex; flex-wrap: wrap; gap: 3px; }
.tag-list.collapsed { max-height: 100px; overflow: hidden; }
.tag-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 11px;
  cursor: pointer;
  color: var(--text-muted);
  white-space: nowrap;
  transition: all 0.15s;
}
.tag-btn:hover { border-color: var(--accent); color: var(--text); }
.tag-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.tag-count { font-size: 9px; opacity: 0.7; }
.tag-toggle {
  background: none; border: none;
  color: var(--accent); font-size: 11px;
  cursor: pointer; padding: 3px 0; display: none;
}
.tag-toggle.visible { display: block; }

/* ── Overlay (mobile) ── */
.overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.4); z-index: 105;
}

/* ── Main content ── */
.main {
  position: fixed;
  top: var(--toolbar-h);
  left: var(--sidebar-w);
  right: 0;
  bottom: 0;
  overflow-y: auto;
}
.feed-list { /* container for all rows */ }

/* ── List row (compact) ── */
.row {
  display: flex;
  align-items: center;
  height: var(--row-h);
  padding: 0 12px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  gap: 8px;
  transition: background 0.1s;
  overflow: hidden;
}
.row:hover { background: var(--bg-row-hover); }
.row.read { opacity: 0.55; }
.row.read:hover { opacity: 0.75; }
.row.expanded { background: var(--bg-row-hover); }
.row .new-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--new-badge);
  flex-shrink: 0;
  visibility: hidden;
}
.row .new-dot.visible { visibility: visible; }
.row-channel {
  display: flex; align-items: center; gap: 4px;
  flex: 0 0 140px;
  overflow: hidden;
}
.row-channel-dot {
  width: 6px; height: 6px;
  border-radius: 1px;
  flex-shrink: 0;
}
.row-channel-name {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-title {
  font-weight: 600;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 0;
  max-width: 45%;
}
.row.read .row-title { font-weight: 400; color: var(--text-muted); }
.row-preview {
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
  font-size: 12px;
}
.row-date {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  text-align: right;
  min-width: 50px;
}
.row-icons {
  display: flex; gap: 3px; flex-shrink: 0;
}
.icon { display: inline-block; width: 12px; height: 12px; border-radius: 2px; vertical-align: middle; }
.icon-img { background: #e67e22; }
.icon-vid { background: #e74c3c; }
.icon-file { background: #8e44ad; }

/* ── Expanded post ── */
.expanded-post {
  display: none;
  background: var(--bg-expanded);
  border-bottom: 1px solid var(--border);
  padding: 16px 20px 20px;
  max-width: 750px;
}
.expanded-post.open { display: block; }
.expanded-post .post-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.expanded-post .post-id { font-weight: 600; }
.expanded-post .post-body { font-size: 14px; line-height: 1.7; }
.expanded-post .post-body p { margin-bottom: 0.7em; }
.expanded-post .post-body p:last-child { margin-bottom: 0; }
.expanded-post .post-body a { word-break: break-all; }

/* Post tags */
.post-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 10px; }
.tag-badge {
  display: inline-block;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.tag-badge:hover { background: var(--accent); color: #fff; }

/* Media */
.media { margin: 12px 0; }
.media img, .media video { max-width: 100%; height: auto; border-radius: 4px; display: block; }
.file-link {
  display: inline-block; padding: 4px 10px;
  background: var(--accent-light); border-radius: 3px; font-size: 13px;
}

/* Thread */
.thread { margin-top: 14px; }
.thread summary {
  cursor: pointer; font-weight: 600; font-size: 13px; color: var(--accent);
  padding: 4px 0; list-style: none;
}
.thread summary::-webkit-details-marker { display: none; }
.thread summary::before { content: "\25B6 "; font-size: 10px; }
.thread[open] summary::before { content: "\25BC "; }
.thread-msg {
  padding: 8px 0 8px 14px;
  border-left: 2px solid var(--border);
  margin-top: 6px;
}
.thread-meta { font-size: 11px; color: var(--text-muted); margin-bottom: 3px; }
.thread-file { font-size: 12px; color: var(--text-muted); margin-bottom: 3px; }
.thread-text { font-size: 13px; }
.thread-text p { margin-bottom: 0.4em; }

/* Hidden by filter */
.hidden-by-tag { display: none !important; }
.hidden-by-search { display: none !important; }

/* ── Mobile ── */
@media (max-width: 767px) {
  .hamburger { display: block; }
  .sidebar {
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    width: 260px;
  }
  .sidebar.open { transform: translateX(0); }
  .overlay.open { display: block; }
  .toolbar { left: 0; }
  .main { left: 0; }
  .row-channel { flex: 0 0 80px; }
  .toolbar-search { flex: 0 0 120px; }
}
```

**Step 2: Commit**

```bash
git add scripts/static/reader.css
git commit -m "feat: add BazQux-style CSS for reader redesign"
```

---

### Task 3: JavaScript — new reader logic

**Files:**
- Create: `scripts/static/reader.js`

**Step 1: Create the JavaScript file**

Create `scripts/static/reader.js`. This is a complete rewrite of the reader JS with:
- Sidebar channel navigation (replaces dropdown)
- "Latest" view (all channels merged, sorted by date)
- Compact list view with accordion expand on click
- Client-side text search
- Tag filtering (sidebar + toolbar dropdown)
- Read tracking via localStorage (mark read on expand, not on scroll)
- New post detection
- Theme toggle (dark default)
- Mobile sidebar toggle

```javascript
(function() {
  "use strict";

  // ── Data ──
  var CHANNELS = JSON.parse(document.getElementById("channels-data").textContent);
  var channelSlugs = Object.keys(CHANNELS);
  var activeView = ""; // "latest" or channel slug

  // ── Per-channel state ──
  var states = {};
  var readSets = {};

  function storageKey(slug) {
    return "reader-" + CHANNELS[slug].channelId;
  }

  function loadState(slug) {
    try {
      var raw = localStorage.getItem(storageKey(slug));
      if (raw) return JSON.parse(raw);
    } catch(e) {}
    return null;
  }

  function saveState(slug) {
    try {
      localStorage.setItem(storageKey(slug), JSON.stringify(states[slug]));
    } catch(e) {}
  }

  // Init states
  channelSlugs.forEach(function(slug) {
    var st = loadState(slug);
    var isFirst = !st;
    if (!st) {
      st = { readPosts: [], lastSyncMaxId: CHANNELS[slug].maxId };
    }
    st._isFirstVisit = isFirst;
    states[slug] = st;
    var rs = {};
    for (var i = 0; i < st.readPosts.length; i++) {
      rs[st.readPosts[i]] = true;
    }
    readSets[slug] = rs;
  });

  // ── DOM ──
  var sidebar = document.getElementById("sidebar");
  var overlay = document.getElementById("overlay");
  var hamburger = document.getElementById("hamburger");
  var mainEl = document.getElementById("main");
  var searchInput = document.getElementById("search-input");
  var tagSelect = document.getElementById("tag-select");
  var btnMarkAll = document.getElementById("btn-mark-all");
  var counterEl = document.getElementById("counter");
  var themeToggle = document.getElementById("theme-toggle");

  // ── Sidebar toggle (mobile) ──
  function openSidebar() { sidebar.classList.add("open"); overlay.classList.add("open"); }
  function closeSidebar() { sidebar.classList.remove("open"); overlay.classList.remove("open"); }
  if (hamburger) {
    hamburger.addEventListener("click", function() {
      sidebar.classList.contains("open") ? closeSidebar() : openSidebar();
    });
  }
  if (overlay) overlay.addEventListener("click", closeSidebar);

  // ── Read tracking ──
  function isRead(slug, postId) {
    return !!readSets[slug][postId];
  }

  function markRead(slug, postId) {
    if (readSets[slug][postId]) return;
    readSets[slug][postId] = true;
    states[slug].readPosts.push(postId);
    saveState(slug);
  }

  function isNewPost(slug, postId) {
    var st = states[slug];
    return !st._isFirstVisit && postId > st.lastSyncMaxId && !readSets[slug][postId];
  }

  // ── View switching ──
  function switchView(view) {
    if (activeView === view) return;
    activeView = view;

    // Update sidebar active
    document.querySelectorAll(".channel-item").forEach(function(el) {
      el.classList.toggle("active", el.dataset.view === view);
    });

    // Show/hide feed lists
    document.querySelectorAll(".feed-list").forEach(function(el) {
      el.style.display = (el.dataset.view === view) ? "" : "none";
    });

    // Collapse all expanded posts
    document.querySelectorAll(".expanded-post.open").forEach(function(el) {
      el.classList.remove("open");
    });
    document.querySelectorAll(".row.expanded").forEach(function(el) {
      el.classList.remove("expanded");
    });

    // Update tag select options for this view
    updateTagSelect(view);

    // Clear search
    if (searchInput) searchInput.value = "";
    clearSearchFilter();

    // Clear tag filter
    clearTagFilter();

    // Scroll to top
    mainEl.scrollTop = 0;

    try { localStorage.setItem("reader-active-view", view); } catch(e) {}

    updateAllUI();
  }

  // ── Row click → accordion ──
  function setupRowClicks() {
    document.querySelectorAll(".row").forEach(function(row) {
      row.addEventListener("click", function() {
        var expanded = row.nextElementSibling;
        if (!expanded || !expanded.classList.contains("expanded-post")) return;

        var isOpen = expanded.classList.contains("open");
        expanded.classList.toggle("open");
        row.classList.toggle("expanded");

        if (!isOpen) {
          // Mark as read when expanding
          var slug = row.dataset.slug;
          var pid = parseInt(row.dataset.postId, 10);
          markRead(slug, pid);
          row.classList.add("read");
          row.querySelector(".new-dot").classList.remove("visible");
          updateAllUI();
        }
      });
    });
  }

  // ── Search ──
  function applySearchFilter() {
    var query = (searchInput.value || "").toLowerCase().trim();
    var view = activeView;
    var list = document.querySelector('.feed-list[data-view="' + view + '"]');
    if (!list) return;

    var rows = list.querySelectorAll(".row");
    rows.forEach(function(row) {
      var expanded = row.nextElementSibling;
      if (!query) {
        row.classList.remove("hidden-by-search");
        if (expanded) expanded.classList.remove("hidden-by-search");
      } else {
        var text = (row.dataset.searchText || "").toLowerCase();
        var match = text.indexOf(query) !== -1;
        row.classList.toggle("hidden-by-search", !match);
        if (expanded) expanded.classList.toggle("hidden-by-search", !match);
      }
    });
  }

  function clearSearchFilter() {
    document.querySelectorAll(".hidden-by-search").forEach(function(el) {
      el.classList.remove("hidden-by-search");
    });
  }

  if (searchInput) {
    var searchTimer = null;
    searchInput.addEventListener("input", function() {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(applySearchFilter, 200);
    });
  }

  // ── Tag filtering ──
  function updateTagSelect(view) {
    if (!tagSelect) return;
    // Build tag options from visible rows
    var list = document.querySelector('.feed-list[data-view="' + view + '"]');
    if (!list) return;

    var tagCounts = {};
    list.querySelectorAll(".row").forEach(function(row) {
      var tags = (row.dataset.tags || "").split(",").filter(Boolean);
      tags.forEach(function(t) {
        tagCounts[t] = (tagCounts[t] || 0) + 1;
      });
    });

    var sorted = Object.keys(tagCounts).sort(function(a, b) {
      return tagCounts[b] - tagCounts[a];
    });

    tagSelect.innerHTML = '<option value="">Все теги</option>';
    sorted.forEach(function(tag) {
      var opt = document.createElement("option");
      opt.value = tag;
      opt.textContent = tag + " (" + tagCounts[tag] + ")";
      tagSelect.appendChild(opt);
    });
  }

  function applyTagFilter() {
    var tag = tagSelect ? tagSelect.value : "";
    var view = activeView;
    var list = document.querySelector('.feed-list[data-view="' + view + '"]');
    if (!list) return;

    list.querySelectorAll(".row").forEach(function(row) {
      var expanded = row.nextElementSibling;
      if (!tag) {
        row.classList.remove("hidden-by-tag");
        if (expanded) expanded.classList.remove("hidden-by-tag");
      } else {
        var tags = (row.dataset.tags || "").split(",");
        var match = tags.indexOf(tag) !== -1;
        row.classList.toggle("hidden-by-tag", !match);
        if (expanded) expanded.classList.toggle("hidden-by-tag", !match);
      }
    });

    // Also update sidebar tag buttons
    document.querySelectorAll(".tag-btn").forEach(function(btn) {
      btn.classList.toggle("active", btn.dataset.tag === tag);
    });
  }

  function clearTagFilter() {
    if (tagSelect) tagSelect.value = "";
    document.querySelectorAll(".hidden-by-tag").forEach(function(el) {
      el.classList.remove("hidden-by-tag");
    });
    document.querySelectorAll(".tag-btn.active").forEach(function(btn) {
      btn.classList.remove("active");
    });
  }

  if (tagSelect) {
    tagSelect.addEventListener("change", applyTagFilter);
  }

  // Sidebar tag button clicks
  document.querySelectorAll(".tag-btn").forEach(function(btn) {
    btn.addEventListener("click", function() {
      var tag = btn.dataset.tag;
      if (tagSelect) {
        tagSelect.value = tag || "";
      }
      applyTagFilter();
    });
  });

  // Tag badge clicks (inside expanded posts)
  document.querySelectorAll(".tag-badge").forEach(function(badge) {
    badge.addEventListener("click", function(e) {
      e.stopPropagation();
      var tag = badge.dataset.tag;
      if (tagSelect) {
        tagSelect.value = tag || "";
      }
      applyTagFilter();
    });
  });

  // ── Collapsible tags in sidebar ──
  (function() {
    var tagList = document.querySelector(".tag-list");
    var tagToggleBtn = document.querySelector(".tag-toggle");
    if (!tagList || !tagToggleBtn) return;
    var totalTags = parseInt(tagToggleBtn.dataset.total || "0", 10);

    function updateBtn() {
      var collapsed = tagList.classList.contains("collapsed");
      tagToggleBtn.textContent = collapsed
        ? "\u0415\u0449\u0451 (" + totalTags + ")"
        : "\u0421\u0432\u0435\u0440\u043D\u0443\u0442\u044C";
    }

    tagList.classList.add("collapsed");
    // Check if overflow
    requestAnimationFrame(function() {
      var overflows = tagList.scrollHeight > tagList.clientHeight + 2;
      tagToggleBtn.classList.toggle("visible", overflows);
      if (!overflows) tagList.classList.remove("collapsed");
      try {
        var saved = localStorage.getItem("reader-tags-expanded");
        if (saved === "1" && overflows) tagList.classList.remove("collapsed");
      } catch(e) {}
      updateBtn();
    });

    tagToggleBtn.addEventListener("click", function() {
      tagList.classList.toggle("collapsed");
      try {
        localStorage.setItem("reader-tags-expanded",
          tagList.classList.contains("collapsed") ? "0" : "1");
      } catch(e) {}
      updateBtn();
    });
  })();

  // ── Mark all read ──
  if (btnMarkAll) {
    btnMarkAll.addEventListener("click", function() {
      var view = activeView;
      var list = document.querySelector('.feed-list[data-view="' + view + '"]');
      if (!list) return;

      list.querySelectorAll(".row").forEach(function(row) {
        var slug = row.dataset.slug;
        var pid = parseInt(row.dataset.postId, 10);
        markRead(slug, pid);
      });

      // Update lastSyncMaxId for affected channels
      if (view === "latest") {
        channelSlugs.forEach(function(slug) {
          states[slug].lastSyncMaxId = CHANNELS[slug].maxId;
          saveState(slug);
        });
      } else {
        states[view].lastSyncMaxId = CHANNELS[view].maxId;
        saveState(view);
      }

      updateAllUI();
    });
  }

  // ── UI update ──
  function updateAllUI() {
    // Update row read states and new dots
    document.querySelectorAll(".row").forEach(function(row) {
      var slug = row.dataset.slug;
      var pid = parseInt(row.dataset.postId, 10);
      row.classList.toggle("read", isRead(slug, pid));
      var dot = row.querySelector(".new-dot");
      if (dot) dot.classList.toggle("visible", isNewPost(slug, pid));
    });

    // Update sidebar unread counts
    document.querySelectorAll(".channel-item").forEach(function(item) {
      var view = item.dataset.view;
      var countEl = item.querySelector(".channel-count");
      if (!countEl) return;
      var unread = 0;

      if (view === "latest") {
        channelSlugs.forEach(function(slug) {
          unread += countUnread(slug);
        });
      } else if (CHANNELS[view]) {
        unread = countUnread(view);
      }
      countEl.textContent = unread > 0 ? unread : "";
    });

    // Update toolbar counter
    if (counterEl) {
      var view = activeView;
      var list = document.querySelector('.feed-list[data-view="' + view + '"]');
      if (list) {
        var rows = list.querySelectorAll(".row");
        var total = 0, readCount = 0;
        rows.forEach(function(r) {
          if (!r.classList.contains("hidden-by-tag") && !r.classList.contains("hidden-by-search")) {
            total++;
            if (r.classList.contains("read")) readCount++;
          }
        });
        counterEl.textContent = readCount + " / " + total;
      }
    }
  }

  function countUnread(slug) {
    var count = 0;
    var ch = CHANNELS[slug];
    if (!ch) return 0;
    // Count from channel feed list
    var list = document.querySelector('.feed-list[data-view="' + slug + '"]');
    if (!list) return 0;
    list.querySelectorAll(".row").forEach(function(row) {
      var pid = parseInt(row.dataset.postId, 10);
      if (!readSets[slug][pid]) count++;
    });
    return count;
  }

  // ── Channel sidebar clicks ──
  document.querySelectorAll(".channel-item").forEach(function(item) {
    item.addEventListener("click", function() {
      switchView(item.dataset.view);
      closeSidebar();
    });
  });

  // ── Theme toggle ──
  function applyTheme(light) {
    document.body.classList.toggle("light", light);
    if (themeToggle) themeToggle.textContent = light ? "\uD83C\uDF19" : "\u2600\uFE0F";
    try { localStorage.setItem("reader-theme", light ? "light" : "dark"); } catch(e) {}
  }

  var savedTheme = "";
  try { savedTheme = localStorage.getItem("reader-theme"); } catch(e) {}
  // Default to dark
  var isLight = savedTheme === "light";
  applyTheme(isLight);

  if (themeToggle) {
    themeToggle.addEventListener("click", function() {
      applyTheme(!document.body.classList.contains("light"));
    });
  }

  // ── Init ──
  setupRowClicks();

  var savedView = "";
  try { savedView = localStorage.getItem("reader-active-view") || ""; } catch(e) {}
  if (savedView !== "latest" && channelSlugs.indexOf(savedView) === -1) {
    savedView = "latest";
  }
  switchView(savedView);
})();
```

**Step 2: Commit**

```bash
git add scripts/static/reader.js
git commit -m "feat: add BazQux-style JavaScript for reader redesign"
```

---

### Task 4: Jinja2 templates — layout and macros

**Files:**
- Create: `scripts/templates/macros.html`
- Create: `scripts/templates/reader.html`

**Step 1: Create macros template**

Create `scripts/templates/macros.html`:

```jinja2
{# ── Post list row (compact) ── #}
{% macro post_row(post) %}
<div class="row"
     data-slug="{{ post.slug }}"
     data-post-id="{{ post.id }}"
     data-tags="{{ post.tags_str }}"
     data-search-text="{{ post.search_text }}">
  <span class="new-dot"></span>
  <div class="row-channel">
    <span class="row-channel-dot" style="background:{{ post.channel_color }}"></span>
    <span class="row-channel-name">{{ post.channel_name }}</span>
  </div>
  <span class="row-title">{{ post.title }}</span>
  {% if post.preview %}<span class="row-preview"> — {{ post.preview }}</span>{% endif %}
  <span class="row-icons">
    {% if post.media_icon_class %}<span class="icon {{ post.media_icon_class }}"></span>{% endif %}
  </span>
  <span class="row-date">{{ post.date_compact }}</span>
</div>
<div class="expanded-post">
  <div class="post-meta">
    <span class="post-id">#{{ post.id }}</span>
    <span>{{ post.date_full }}</span>
    <span style="color:{{ post.channel_color }}">{{ post.channel_name }}</span>
  </div>
  {{ post.media_html }}
  <div class="post-body">{{ post.text_html }}</div>
  {% if post.tags %}
  <div class="post-tags">
    {% for tag in post.tags %}
    <span class="tag-badge" data-tag="{{ tag }}">{{ tag }}</span>
    {% endfor %}
  </div>
  {% endif %}
  {{ post.thread_html }}
</div>
{% endmacro %}
```

**Step 2: Create main template**

Create `scripts/templates/reader.html`:

```jinja2
{% from "macros.html" import post_row %}
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TeleShelf Reader</title>
<style>
{{ css }}
</style>
</head>
<body>

<script id="channels-data" type="application/json">
{{ channels_json }}
</script>

{# ── Sidebar ── #}
<nav id="sidebar" class="sidebar">
  <div class="sidebar-header">TeleShelf</div>
  <div class="sidebar-channels">
    <div class="channel-item active" data-view="latest">
      <span class="channel-dot" style="background:var(--accent)"></span>
      <span class="channel-name">Latest</span>
      <span class="channel-count"></span>
    </div>
    {% for ch in channels %}
    <div class="channel-item" data-view="{{ ch.slug }}">
      <span class="channel-dot" style="background:{{ ch.color }}"></span>
      <span class="channel-name">{{ ch.name }}</span>
      <span class="channel-count"></span>
    </div>
    {% endfor %}
  </div>
  {% if all_tags %}
  <div class="sidebar-tags">
    <div class="sidebar-tags-label">Теги</div>
    <div class="tag-list collapsed">
      <button class="tag-btn active" data-tag="">все</button>
      {% for tag_name, count in all_tags %}
      <button class="tag-btn" data-tag="{{ tag_name }}">{{ tag_name }} <span class="tag-count">&middot;{{ count }}</span></button>
      {% endfor %}
    </div>
    <button class="tag-toggle" data-total="{{ all_tags|length }}"></button>
  </div>
  {% endif %}
</nav>

{# ── Overlay (mobile) ── #}
<div id="overlay" class="overlay"></div>

{# ── Toolbar ── #}
<header class="toolbar">
  <button id="hamburger" class="hamburger" aria-label="Menu">&#9776;</button>
  <input id="search-input" class="toolbar-search" type="text" placeholder="Поиск...">
  <select id="tag-select" class="toolbar-tag-select">
    <option value="">Все теги</option>
  </select>
  <span class="toolbar-spacer"></span>
  <span id="counter" class="toolbar-counter"></span>
  <button id="btn-mark-all" class="toolbar-btn">Прочитать все</button>
  <button id="theme-toggle" class="theme-toggle" aria-label="Toggle theme"></button>
</header>

{# ── Main content ── #}
<main id="main" class="main">
  {# Latest (all channels merged by date desc) #}
  <div class="feed-list" data-view="latest">
    {% for post in all_posts %}
    {{ post_row(post) }}
    {% endfor %}
  </div>

  {# Per-channel lists #}
  {% for ch in channels %}
  <div class="feed-list" data-view="{{ ch.slug }}" style="display:none">
    {% for post in ch.posts %}
    {{ post_row(post) }}
    {% endfor %}
  </div>
  {% endfor %}
</main>

<script>
{{ js }}
</script>
</body>
</html>
```

**Step 3: Commit**

```bash
git add scripts/templates/macros.html scripts/templates/reader.html
git commit -m "feat: add Jinja2 templates for BazQux-style reader"
```

---

### Task 5: Refactor build_reader.py — Jinja2 integration

**Files:**
- Modify: `scripts/build_reader.py` (full rewrite, keep data loading functions)

**Step 1: Rewrite build_reader.py**

Keep the following helper functions from the existing file (unchanged):
- `format_date`, `escape`, `format_text`, `file_ext`, `get_media_html`, `media_icon` (rename to `media_icon_class`), `short_date`, `load_thread`, `render_thread_message`, `load_channel`

Remove:
- `CSS` and `JS` string constants
- `render_channel_sidebar`, `render_channel_content` functions
- The HTML assembly in `build_combined_reader`

Add:
- `extract_title_preview(text)` — extracts title (first ~60 chars) and preview (next ~120 chars)
- `compact_date(unix_ts)` — returns "21 фев" style date
- `prepare_post(msg, channel, media_base)` — prepares a post dict for the template
- `build_combined_reader()` — loads data, prepares template context, renders via Jinja2

The complete file:

```python
#!/usr/bin/env python3
"""
build_reader.py — Generate a BazQux-style reader for all Telegram channels.

Usage:
    python3 scripts/build_reader.py

Scans downloads/*/ for channels with channel.json and all-messages.json.
Writes reader/index.html in the project root.
"""

import html
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

from jinja2 import Environment, FileSystemLoader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOSCOW_TZ = timezone(timedelta(hours=3))

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

MONTHS_RU_SHORT = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр",
    5: "май", 6: "июн", 7: "июл", 8: "авг",
    9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

CHANNEL_COLORS = [
    "#e8a838", "#4a9eff", "#e74c3c", "#2ecc71",
    "#9b59b6", "#1abc9c", "#e67e22", "#3498db",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def format_date(unix_ts: int) -> str:
    dt = datetime.fromtimestamp(unix_ts, tz=MOSCOW_TZ)
    return f"{dt.day} {MONTHS_RU[dt.month]} {dt.year}, {dt.strftime('%H:%M')}"


def compact_date(unix_ts: int) -> str:
    dt = datetime.fromtimestamp(unix_ts, tz=MOSCOW_TZ)
    return f"{dt.day} {MONTHS_RU_SHORT[dt.month]}"


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def format_text(text: str) -> str:
    if not text:
        return ""
    escaped = escape(text)
    escaped = re.sub(
        r'(https?://[^\s<>&]+)',
        r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    paragraphs = re.split(r'\n{2,}', escaped)
    parts = []
    for p in paragraphs:
        p = p.strip()
        if p:
            inner = p.replace("\n", "<br>\n")
            parts.append(f"<p>{inner}</p>")
    return "\n".join(parts)


def file_ext(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()


def get_media_html(media_base: str, channel_id: str, post_id: int, file_field: str) -> str:
    if not file_field:
        return ""
    media_filename = f"{channel_id}_{post_id}_{file_field}"
    rel_path = f"{media_base}/{media_filename}"
    escaped_path = escape(rel_path)
    escaped_name = escape(file_field)
    ext = file_ext(file_field)
    if ext in IMAGE_EXTS:
        return f'<div class="media"><img src="{escaped_path}" alt="Post {post_id}" loading="lazy"></div>'
    if ext in VIDEO_EXTS:
        return f'<div class="media"><video src="{escaped_path}" controls preload="none"></video></div>'
    return f'<div class="media"><a href="{escaped_path}" download class="file-link">{escaped_name}</a></div>'


def media_icon_class(file_field: str) -> str:
    if not file_field:
        return ""
    ext = file_ext(file_field)
    if ext in IMAGE_EXTS:
        return "icon-img"
    if ext in VIDEO_EXTS:
        return "icon-vid"
    return "icon-file"


def load_thread(threads_dir: str, post_id: int) -> list:
    path = os.path.join(threads_dir, f"thread-{post_id}.json")
    if not os.path.isfile(path):
        path = os.path.join(threads_dir, f"thread-{post_id}-channel.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("messages", []) or []
    except (json.JSONDecodeError, KeyError):
        return []


def render_thread_message(msg: dict) -> str:
    msg_id = msg.get("id", "")
    date_ts = msg.get("date", 0)
    text = msg.get("text", "")
    file_field = msg.get("file", "")
    parts = ['<div class="thread-msg">']
    parts.append(f'<div class="thread-meta">#{msg_id} &middot; {escape(format_date(date_ts))}</div>')
    if file_field:
        parts.append(f'<div class="thread-file">{escape(file_field)}</div>')
    if text:
        parts.append(f'<div class="thread-text">{format_text(text)}</div>')
    parts.append('</div>')
    return "\n".join(parts)


def extract_title_preview(text: str, title_len: int = 60, preview_len: int = 120) -> tuple:
    if not text:
        return "", ""
    clean = text.replace("\n", " ").strip()
    clean = re.sub(r'\s+', ' ', clean)
    if len(clean) <= title_len:
        return clean, ""
    title = clean[:title_len]
    last_space = title.rfind(" ")
    if last_space > title_len // 2:
        title = title[:last_space]
    preview = clean[len(title):len(title) + preview_len].strip()
    if len(clean) > len(title) + preview_len:
        preview += "..."
    return title, preview


# ---------------------------------------------------------------------------
# Channel data loader
# ---------------------------------------------------------------------------

def load_channel(slug: str, base_dir: str) -> dict:
    config_path = os.path.join(base_dir, "channel.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    messages_path = os.path.join(base_dir, "channel-full", "all-messages.json")
    with open(messages_path, "r", encoding="utf-8") as f:
        messages_data = json.load(f)
    messages = messages_data.get("messages", [])
    messages.sort(key=lambda m: m["id"])

    tags = {}
    tags_path = os.path.join(base_dir, "tags.json")
    if os.path.isfile(tags_path):
        with open(tags_path, "r", encoding="utf-8") as f:
            tags = json.load(f)

    tag_counts = {}
    for post_tags in tags.values():
        for t in post_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])

    return {
        "slug": slug,
        "config": config,
        "messages": messages,
        "tags": tags,
        "tag_counts": tag_counts,
        "sorted_tags": sorted_tags,
        "threads_dir": os.path.join(base_dir, "threads"),
    }


# ---------------------------------------------------------------------------
# Post preparation for template
# ---------------------------------------------------------------------------

def prepare_post(msg: dict, channel: dict, media_base: str, channel_color: str) -> dict:
    slug = channel["slug"]
    config = channel["config"]
    channel_id = config["channel_id"]
    tags = channel["tags"]
    threads_dir = channel["threads_dir"]

    pid = msg["id"]
    date_ts = msg.get("date", 0)
    text = msg.get("text", "")
    file_field = msg.get("file", "")

    title, preview = extract_title_preview(text)
    post_tags = tags.get(str(pid), [])

    thread_html = ""
    thread_messages = load_thread(threads_dir, pid)
    if thread_messages:
        count = len(thread_messages)
        thread_comments = "\n".join(render_thread_message(tm) for tm in thread_messages)
        thread_html = (
            f'<details class="thread">'
            f'<summary>Комментарии ({count})</summary>'
            f'{thread_comments}'
            f'</details>'
        )

    return {
        "slug": slug,
        "id": pid,
        "channel_name": config.get("name", slug),
        "channel_color": channel_color,
        "title": escape(title),
        "preview": escape(preview),
        "date_compact": compact_date(date_ts),
        "date_full": format_date(date_ts),
        "date_ts": date_ts,
        "text_html": format_text(text),
        "media_html": get_media_html(media_base, channel_id, pid, file_field),
        "media_icon_class": media_icon_class(file_field),
        "tags": post_tags,
        "tags_str": ",".join(post_tags),
        "search_text": escape(text.replace("\n", " ")[:300]),
        "thread_html": thread_html,
    }


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_combined_reader() -> None:
    downloads_dir = "downloads"
    if not os.path.isdir(downloads_dir):
        print("Error: downloads/ directory not found.", file=sys.stderr)
        sys.exit(1)

    # Find all channels
    channels_raw = []
    for slug in sorted(os.listdir(downloads_dir)):
        channel_dir = os.path.join(downloads_dir, slug)
        config_path = os.path.join(channel_dir, "channel.json")
        messages_path = os.path.join(channel_dir, "channel-full", "all-messages.json")
        if os.path.isfile(config_path) and os.path.isfile(messages_path):
            channels_raw.append(load_channel(slug, channel_dir))

    if not channels_raw:
        print("Error: no channels found in downloads/.", file=sys.stderr)
        sys.exit(1)

    # Assign colors and prepare posts
    channels_data = []
    all_posts = []
    all_tag_counts = {}

    for idx, ch in enumerate(channels_raw):
        color = CHANNEL_COLORS[idx % len(CHANNEL_COLORS)]
        media_base = f"../downloads/{ch['slug']}/channel-main"

        posts = []
        for msg in ch["messages"]:
            post = prepare_post(msg, ch, media_base, color)
            posts.append(post)

        # Merge tag counts
        for tag, count in ch["tag_counts"].items():
            all_tag_counts[tag] = all_tag_counts.get(tag, 0) + count

        messages = ch["messages"]
        max_id = max(m["id"] for m in messages) if messages else 0

        channels_data.append({
            "slug": ch["slug"],
            "name": ch["config"].get("name", ch["slug"]),
            "color": color,
            "posts": posts,
            "max_id": max_id,
            "total_posts": len(messages),
        })

        all_posts.extend(posts)

    # Sort all_posts by date descending (newest first)
    all_posts.sort(key=lambda p: p["date_ts"], reverse=True)

    # All tags sorted by count
    all_tags = sorted(all_tag_counts.items(), key=lambda x: -x[1])

    # Build channels JSON for JS
    channels_js_data = {}
    for ch in channels_data:
        channels_js_data[ch["slug"]] = {
            "channelId": next(
                cr["config"]["channel_id"]
                for cr in channels_raw if cr["slug"] == ch["slug"]
            ),
            "maxId": ch["max_id"],
            "totalPosts": ch["total_posts"],
            "name": ch["name"],
        }

    # Load CSS and JS from static files
    css_path = os.path.join(SCRIPT_DIR, "static", "reader.css")
    js_path = os.path.join(SCRIPT_DIR, "static", "reader.js")

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Render template
    env = Environment(
        loader=FileSystemLoader(os.path.join(SCRIPT_DIR, "templates")),
        autoescape=False,
    )
    template = env.get_template("reader.html")

    html_output = template.render(
        css=css,
        js=js,
        channels=channels_data,
        all_posts=all_posts,
        all_tags=all_tags,
        channels_json=json.dumps(channels_js_data, ensure_ascii=False),
    )

    # Write output
    reader_dir = "reader"
    os.makedirs(reader_dir, exist_ok=True)
    output_path = os.path.join(reader_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_output)

    print(f"Built combined reader: {output_path}")
    for ch in channels_data:
        print(f"  {ch['name']}: {ch['total_posts']} posts")
    print(f"  All posts: {len(all_posts)}, Tags: {len(all_tags)}")


if __name__ == "__main__":
    build_combined_reader()
```

**Step 2: Run the build**

Run: `python3 scripts/build_reader.py`
Expected: Outputs "Built combined reader: reader/index.html" with channel stats.

**Step 3: Verify visually**

Run: `open reader/index.html`
Expected: BazQux-style dark reader with sidebar channels, compact list view, working accordion, search, tag filter.

**Step 4: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: rewrite build_reader.py with Jinja2 and BazQux layout"
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update the Static HTML Reader section**

In `CLAUDE.md`, find the `## Static HTML Reader` section and replace it with the updated description reflecting the new BazQux-style design:

```markdown
## Static HTML Reader

A single combined `reader/index.html` serves all channels in a BazQux-style interface.

### Features
- **BazQux-style layout** — sidebar with channel list, compact list view in main area
- **Channel sidebar** — "Latest" (all channels) + per-channel entries with unread counts
- **Compact list view** — one row per post: channel name, title, preview, date
- **Accordion expand** — click a row to expand full post with media, tags, threads
- **Search** — client-side text search in toolbar
- **Light/dark theme** — toggle in toolbar, dark by default
- **Read tracking** — posts marked as read on expand, persisted per-channel in localStorage
- **New post badges** — posts added after last visit highlighted
- **Tag filtering** — sidebar tags + toolbar dropdown
- **Thread display** — inline thread messages in expanded posts
- **Fully offline** — single HTML file, no external dependencies

### Build architecture
- `scripts/build_reader.py` — data loading + Jinja2 rendering
- `scripts/templates/reader.html` — main HTML template
- `scripts/templates/macros.html` — reusable macros (post row, expanded view)
- `scripts/static/reader.css` — BazQux-style CSS
- `scripts/static/reader.js` — reader logic (channel switching, search, tags, read tracking)
- CSS/JS are inlined into the final `reader/index.html` at build time
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with new reader architecture"
```
