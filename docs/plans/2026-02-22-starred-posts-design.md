# Starred Posts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ability to star/favorite individual posts and filter to show only starred posts.

**Architecture:** Star state stored in a single global localStorage key. Star button in each post row (Gmail-style, left side). Toolbar toggle + sidebar entry to filter starred posts. Filtering uses the same `hidden-by-*` CSS class pattern as tags/search.

**Tech Stack:** Vanilla JS, CSS, Jinja2 templates

**Issue:** #2

---

### Task 1: Add star button to post row template

**Files:**
- Modify: `scripts/templates/macros.html:8` (between `new-dot` and `row-channel`)

**Step 1: Add star button element**

In `scripts/templates/macros.html`, between `<span class="new-dot"></span>` (line 8) and `<div class="row-channel">` (line 9), insert:

```html
  <button class="star-btn" aria-label="Star">&#9734;</button>
```

The full row structure becomes:
```html
  <span class="new-dot"></span>
  <button class="star-btn" aria-label="Star">&#9734;</button>
  <div class="row-channel">
```

---

### Task 2: Add star button and filter CSS

**Files:**
- Modify: `scripts/static/reader.css`

**Step 1: Add star button styles**

After `.row .new-dot.visible { visibility: visible; }` (line 240), add:

```css
.star-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0;
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.4;
  transition: opacity 0.15s;
}
.row:hover .star-btn { opacity: 0.7; }
.star-btn.starred {
  color: var(--accent);
  opacity: 1;
}
.star-btn.starred:hover { opacity: 0.8; }
```

**Step 2: Add hidden-by-star filter class**

After `.hidden-by-search` (line 359), add:

```css
.hidden-by-star { display: none !important; }
```

**Step 3: Add toolbar starred button active style**

After `.toolbar-btn:hover` (line 94), add:

```css
.toolbar-btn.active { color: var(--accent); border-color: var(--accent); }
```

---

### Task 3: Add sidebar entry and toolbar button to reader.html

**Files:**
- Modify: `scripts/templates/reader.html`

**Step 1: Add "Starred" sidebar entry**

After the "Latest" channel-item (line 26), before the `{% for ch in channels %}` loop (line 27), insert:

```html
    <div class="channel-item" data-view="starred">
      <span class="channel-dot" style="background:var(--accent)">&#9733;</span>
      <span class="channel-name">Starred</span>
      <span class="channel-count"></span>
    </div>
```

Note: the `channel-dot` reuses the 8x8 dot but with a small star glyph inside — alternatively, style it as text. We use `data-view="starred"` as a virtual view handled in JS.

**Step 2: Add toolbar starred toggle button**

After the `</select>` for tag-select (line 58), before `<span class="toolbar-spacer">` (line 59), insert:

```html
  <button id="btn-starred" class="toolbar-btn" aria-label="Show starred only">&#9733; Starred</button>
```

---

### Task 4: Implement star logic in reader.js

**Files:**
- Modify: `scripts/static/reader.js`

This is the largest task. All changes are within the existing IIFE.

**Step 1: Add starred state storage (after readSets init, line 11)**

After `var readSets = {};` (line 11), add:

```js
  // ── Starred state (global, cross-channel) ──
  var starredSet = {};
  (function() {
    try {
      var raw = localStorage.getItem("reader-starred");
      if (raw) starredSet = JSON.parse(raw);
    } catch(e) {}
  })();

  function starKey(slug, postId) { return slug + ":" + postId; }

  function isStarred(slug, postId) {
    return !!starredSet[starKey(slug, postId)];
  }

  function toggleStar(slug, postId) {
    var key = starKey(slug, postId);
    if (starredSet[key]) {
      delete starredSet[key];
    } else {
      starredSet[key] = true;
    }
    try {
      localStorage.setItem("reader-starred", JSON.stringify(starredSet));
    } catch(e) {}
  }
```

**Step 2: Add star filter state and DOM refs (after themeToggle ref, line 56)**

After `var themeToggle = document.getElementById("theme-toggle");` (line 56), add:

```js
  var btnStarred = document.getElementById("btn-starred");
  var starFilterActive = false;
```

**Step 3: Add star filter functions (after clearTagFilter, line 246)**

After the `clearTagFilter` function block (line 246), add:

```js
  // ── Star filtering ──
  function applyStarFilter() {
    var view = activeView;
    var list = document.querySelector('.feed-list[data-view="' + view + '"]');
    if (!list) return;

    list.querySelectorAll(".row").forEach(function(row) {
      var expanded = row.nextElementSibling;
      if (!starFilterActive) {
        row.classList.remove("hidden-by-star");
        if (expanded) expanded.classList.remove("hidden-by-star");
      } else {
        var slug = row.dataset.slug;
        var pid = parseInt(row.dataset.postId, 10);
        var match = isStarred(slug, pid);
        row.classList.toggle("hidden-by-star", !match);
        if (expanded) expanded.classList.toggle("hidden-by-star", !match);
      }
    });

    if (btnStarred) btnStarred.classList.toggle("active", starFilterActive);
    updateAllUI();
  }

  function clearStarFilter() {
    starFilterActive = false;
    document.querySelectorAll(".hidden-by-star").forEach(function(el) {
      el.classList.remove("hidden-by-star");
    });
    if (btnStarred) btnStarred.classList.remove("active");
  }
```

**Step 4: Add star filter reset to switchView (line 116)**

In `switchView`, after `clearTagFilter();` (line 116), add:

```js
    // Clear star filter
    clearStarFilter();
```

**Step 5: Wire up toolbar starred button (after tagSelect event listener, line 250)**

After the tag-related event listeners section, add:

```js
  // ── Star toggle button ──
  if (btnStarred) {
    btnStarred.addEventListener("click", function() {
      starFilterActive = !starFilterActive;
      applyStarFilter();
    });
  }
```

**Step 6: Wire up star buttons on rows (inside setupRowClicks, line 128)**

Inside `setupRowClicks`, before the existing `row.addEventListener("click", ...)` (line 129), add a listener for the star button:

```js
      var starBtn = row.querySelector(".star-btn");
      if (starBtn) {
        starBtn.addEventListener("click", function(e) {
          e.stopPropagation();
          var slug = row.dataset.slug;
          var pid = parseInt(row.dataset.postId, 10);
          toggleStar(slug, pid);
          updateStarButtons(slug, pid);
          updateAllUI();
        });
      }
```

**Step 7: Add updateStarButtons helper (after toggleStar function)**

After the `toggleStar` function, add:

```js
  function updateStarButtons(slug, postId) {
    var starred = isStarred(slug, postId);
    document.querySelectorAll('.row[data-slug="' + slug + '"][data-post-id="' + postId + '"]').forEach(function(row) {
      var btn = row.querySelector(".star-btn");
      if (btn) {
        btn.classList.toggle("starred", starred);
        btn.innerHTML = starred ? "&#9733;" : "&#9734;";
      }
    });
  }
```

**Step 8: Update updateAllUI to handle stars (line 339)**

In `updateAllUI`, inside the `document.querySelectorAll(".row").forEach` loop (line 340), after the new-dot toggle (line 345), add:

```js
      var starBtn = row.querySelector(".star-btn");
      if (starBtn) {
        var starred = isStarred(slug, pid);
        starBtn.classList.toggle("starred", starred);
        starBtn.innerHTML = starred ? "&#9733;" : "&#9734;";
      }
```

**Step 9: Update counter to respect star filter (line 371)**

Change the counter filter condition from:

```js
          if (!r.classList.contains("hidden-by-tag") && !r.classList.contains("hidden-by-search")) {
```

to:

```js
          if (!r.classList.contains("hidden-by-tag") && !r.classList.contains("hidden-by-search") && !r.classList.contains("hidden-by-star")) {
```

**Step 10: Handle "Starred" sidebar entry (line 393)**

In the channel sidebar click handler, the `switchView("starred")` call needs special handling. Update `switchView` to handle the "starred" virtual view:

At the beginning of `switchView` (line 86), after `activeView = view;`, add handling for the starred view — when "starred" is selected, show the "latest" feed-list but activate the star filter:

Replace the `switchView` function body. After `activeView = view;` (line 88) and before `// Update sidebar active` (line 90), add:

```js
    var feedView = (view === "starred") ? "latest" : view;
```

Then change all references to `view` in the feed-list show/hide logic (line 97) to use `feedView`:

```js
      el.style.display = (el.dataset.view === feedView) ? "" : "none";
```

And after `clearStarFilter();` (the line we added in Step 4), add:

```js
    // Activate star filter for starred view
    if (view === "starred") {
      starFilterActive = true;
      applyStarFilter();
    }
```

Also update `updateTagSelect(view)` (line 109) to use `feedView`:

```js
    updateTagSelect(feedView);
```

And update the `localStorage.setItem` (line 121) and the counter's `activeView` usage: the counter should use `feedView` too. Add `var feedViewForCounter = (activeView === "starred") ? "latest" : activeView;` at the top of `updateAllUI` and use it for the feed-list query.

**Step 11: Update starred count in sidebar**

In `updateAllUI`, inside the `.channel-item` forEach (line 348), add a case for the "starred" view:

After the `} else if (CHANNELS[view]) {` block (line 360), add:

```js
      } else if (view === "starred") {
        var starCount = Object.keys(starredSet).length;
        countEl.textContent = starCount > 0 ? starCount : "";
        return;
```

**Step 12: Update saved view restore to handle "starred"**

In the init section (line 423), update the saved view validation:

```js
  if (savedView !== "latest" && savedView !== "starred" && channelSlugs.indexOf(savedView) === -1) {
```

---

### Task 5: Build reader and verify

**Step 1: Build the reader**

Run: `task build-reader`

**Step 2: Open and verify**

Run: `open reader/index.html`

Verify:
- Star icons (☆) appear on each post row, left side before channel name
- Clicking star toggles to filled (★) gold — does NOT expand the post
- Stars persist after page reload
- "Starred" toolbar button filters current view to show only starred posts
- "Starred" sidebar entry shows starred posts count and filters to starred-only
- Counter in toolbar respects star filter
- Star filter resets when switching between channels

---

### Task 6: Commit

**Step 1: Stage and commit**

```bash
git add scripts/static/reader.js scripts/static/reader.css scripts/templates/macros.html scripts/templates/reader.html
git commit -m "feat: add star/favorite posts with filtering

Closes #2"
```
