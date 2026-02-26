# Reader QoL Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add keyboard navigation, fix mobile toolbar, add empty states, fix text-less posts, remove search limit.

**Architecture:** All changes are in 4 files: `reader.js` (keyboard nav + empty states), `reader.css` (focus style + mobile + empty states), `reader.html` (empty state divs), `build_reader.py` (fallback titles + search limit). No new dependencies.

**Tech Stack:** Vanilla JS, CSS, Python/Jinja2

**Design doc:** `docs/plans/2026-02-26-reader-qol-design.md`

---

### Task 1: Remove search text 300-char limit

**Files:**
- Modify: `scripts/build_reader.py:344`

**Step 1: Remove the [:300] truncation**

In `scripts/build_reader.py`, line 344, change:

```python
        "search_text": escape(text.replace("\n", " ")[:300]),
```

to:

```python
        "search_text": escape(text.replace("\n", " ")),
```

**Step 2: Rebuild and verify**

Run: `python3 scripts/build_reader.py`

Expected: Builds successfully. Verify a long post's `data-search-text` contains more than 300 chars:

```bash
grep -oP 'data-search-text="[^"]{300,400}' reader/index.html | head -1
```

Expected: At least one match (a post with 300+ chars of text).

**Step 3: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat(reader): remove 300-char search text limit for full-text search"
```

---

### Task 2: Fallback display for posts without text

**Files:**
- Modify: `scripts/build_reader.py:243-257` (`extract_title_preview` function)
- Modify: `scripts/build_reader.py:302-346` (`prepare_post` function)
- Modify: `scripts/static/reader.css` (add `.row-title-fallback` style)

**Step 1: Modify extract_title_preview to accept file_field**

In `scripts/build_reader.py`, replace the `extract_title_preview` function (lines 243-257) with:

```python
IMAGE_EXTS_SET = IMAGE_EXTS  # already defined at top of file

def extract_title_preview(text: str, file_field: str = "", title_len: int = 60, preview_len: int = 120) -> tuple:
    if not text:
        if file_field:
            ext = file_ext(file_field)
            if ext in IMAGE_EXTS:
                return "[Фото]", ""
            if ext in VIDEO_EXTS:
                return "[Видео]", ""
            return f"[Файл: {file_field}]", ""
        return "[Пустой пост]", ""
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
```

**Step 2: Pass file_field to extract_title_preview in prepare_post**

In `scripts/build_reader.py`, line 314, change:

```python
    title, preview = extract_title_preview(text)
```

to:

```python
    title, preview = extract_title_preview(text, file_field)
```

**Step 3: Add a flag for fallback titles in the post dict**

In `prepare_post`, add an `is_fallback_title` field. After line 314 (the `extract_title_preview` call), add:

```python
    is_fallback_title = not text
```

And in the return dict (line 329+), add:

```python
        "is_fallback_title": is_fallback_title,
```

**Step 4: Update the macros.html template to use fallback styling**

In `scripts/templates/macros.html`, line 14, change:

```html
  <span class="row-title">{{ post.title }}</span>
```

to:

```html
  <span class="row-title{% if post.is_fallback_title %} row-title-fallback{% endif %}">{{ post.title }}</span>
```

**Step 5: Add CSS for fallback titles**

In `scripts/static/reader.css`, after the `.row-title` block (after line 290), add:

```css
.row-title-fallback { font-weight: 400; font-style: italic; color: var(--text-muted); }
```

**Step 6: Rebuild and verify**

Run: `python3 scripts/build_reader.py`

Expected: Builds successfully. Check that posts without text now show fallback titles:

```bash
grep -o 'row-title-fallback' reader/index.html | wc -l
```

Expected: Count > 0 if any text-less posts exist. If all posts have text, count may be 0 — that's OK, the logic is still correct.

**Step 7: Commit**

```bash
git add scripts/build_reader.py scripts/templates/macros.html scripts/static/reader.css
git commit -m "feat(reader): show fallback titles for posts without text"
```

---

### Task 3: Mobile toolbar — hide non-essential elements

**Files:**
- Modify: `scripts/static/reader.css:393-406` (mobile `@media` block)

**Step 1: Add display:none rules for mobile**

In `scripts/static/reader.css`, inside the `@media (max-width: 767px)` block (lines 393-406), before the closing `}`, add:

```css
  .toolbar-tag-select { display: none; }
  #btn-starred { display: none; }
  #counter { display: none; }
  #btn-export { display: none; }
  #btn-import { display: none; }
```

**Step 2: Rebuild and verify**

Run: `python3 scripts/build_reader.py`

Expected: Builds successfully. Visually verify by resizing browser window to <767px — only hamburger, search, "Прочитать все", and theme toggle should be visible in toolbar.

**Step 3: Commit**

```bash
git add scripts/static/reader.css
git commit -m "feat(reader): hide non-essential toolbar elements on mobile"
```

---

### Task 4: Empty states for search/tag/star filters

**Files:**
- Modify: `scripts/templates/reader.html:80-96` (add empty-state divs to feed-lists)
- Modify: `scripts/static/reader.css` (add `.empty-state` styles)
- Modify: `scripts/static/reader.js` (add `updateEmptyState` function, call it from filters)

**Step 1: Add empty-state divs to the template**

In `scripts/templates/reader.html`, add an empty-state div inside each feed-list.

Change the "Latest" feed-list (lines 82-86):

```html
  <div class="feed-list" data-view="latest">
    {% for post in all_posts %}
    {{ post_row(post) }}
    {% endfor %}
    <div class="empty-state" style="display:none">Ничего не найдено</div>
  </div>
```

Change the per-channel loop (lines 89-95):

```html
  {% for ch in channels %}
  <div class="feed-list" data-view="{{ ch.slug }}" style="display:none">
    {% for post in ch.posts %}
    {{ post_row(post) }}
    {% endfor %}
    <div class="empty-state" style="display:none">Ничего не найдено</div>
  </div>
  {% endfor %}
```

**Step 2: Add CSS for empty-state**

In `scripts/static/reader.css`, after the `/* Hidden by filter */` section (after line 390), add:

```css
.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}
```

**Step 3: Add updateEmptyState function to reader.js**

In `scripts/static/reader.js`, add a new function after the `clearStarFilter` function (after line 531) and before the sidebar tag button clicks section:

```javascript
  // ── Empty state ──
  function updateEmptyState() {
    var feedView = (activeView === "starred") ? "latest" : activeView;
    var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
    if (!list) return;

    var emptyEl = list.querySelector(".empty-state");
    if (!emptyEl) return;

    var hasVisible = false;
    var rows = list.querySelectorAll(".row");
    for (var i = 0; i < rows.length; i++) {
      if (!rows[i].classList.contains("hidden-by-tag") &&
          !rows[i].classList.contains("hidden-by-search") &&
          !rows[i].classList.contains("hidden-by-star")) {
        hasVisible = true;
        break;
      }
    }

    if (hasVisible) {
      emptyEl.style.display = "none";
    } else {
      // Determine message based on active filters
      var msg = "Ничего не найдено";
      var searchQuery = searchInput ? searchInput.value.trim() : "";
      var tagValue = tagSelect ? tagSelect.value : "";

      if (starFilterActive && !searchQuery && !tagValue) {
        msg = "Нет избранных постов";
      } else if (tagValue && !searchQuery && !starFilterActive) {
        msg = "Нет постов с тегом «" + tagValue + "»";
      }

      emptyEl.textContent = msg;
      emptyEl.style.display = "";
    }
  }
```

**Step 4: Call updateEmptyState from filter functions**

Add `updateEmptyState();` at the end of these existing functions:

1. `applySearchFilter()` — after the `rows.forEach(...)` loop (after the closing `});` at line 419), add `updateEmptyState();`

2. `applyTagFilter()` — after the tag-btn toggle loop (after line 484), add `updateEmptyState();`

3. `applyStarFilter()` — before the existing `updateAllUI();` call at line 522, add `updateEmptyState();`

4. `clearSearchFilter()` — at the end (after line 425), add `updateEmptyState();`

5. `clearTagFilter()` — at the end (after line 494), add `updateEmptyState();`

6. `clearStarFilter()` — at the end (after line 530), add `updateEmptyState();`

7. `switchView()` — after `updateAllUI();` at line 361, add `updateEmptyState();`

**Step 5: Rebuild and verify**

Run: `python3 scripts/build_reader.py`

Expected: Builds successfully. Open reader, search for a gibberish string — "Ничего не найдено" should appear. Filter by starred with nothing starred — "Нет избранных постов" should appear.

**Step 6: Commit**

```bash
git add scripts/templates/reader.html scripts/static/reader.css scripts/static/reader.js
git commit -m "feat(reader): add empty state messages for search/tag/star filters"
```

---

### Task 5: Keyboard navigation (j/k/n/p/Enter/o/Esc/s//)

**Files:**
- Modify: `scripts/static/reader.js` (add keyboard nav section)
- Modify: `scripts/static/reader.css` (add `.row.focused` style)

**Step 1: Add .focused CSS style**

In `scripts/static/reader.css`, after the `.row.expanded` rule (after line 238), add:

```css
.row.focused { border-left: 3px solid var(--accent); padding-left: 9px; }
```

Note: the original row has `padding: 0 12px`. The focused row gets `border-left: 3px` + `padding-left: 9px` = 12px total, so layout doesn't shift.

**Step 2: Add keyboard navigation section to reader.js**

In `scripts/static/reader.js`, add the following section after the Export/Import button wiring (after line 724) and before the `savedView` variable (before line 726):

```javascript
  // ── Keyboard navigation ──
  var focusedIndex = -1;

  function getVisibleRows() {
    var feedView = (activeView === "starred") ? "latest" : activeView;
    var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
    if (!list) return [];
    var rows = list.querySelectorAll(".row");
    var visible = [];
    for (var i = 0; i < rows.length; i++) {
      if (!rows[i].classList.contains("hidden-by-tag") &&
          !rows[i].classList.contains("hidden-by-search") &&
          !rows[i].classList.contains("hidden-by-star")) {
        visible.push(rows[i]);
      }
    }
    return visible;
  }

  function setFocus(idx) {
    var rows = getVisibleRows();
    // Remove previous focus
    var prev = document.querySelector(".row.focused");
    if (prev) prev.classList.remove("focused");

    if (idx < 0 || idx >= rows.length) {
      focusedIndex = -1;
      return;
    }
    focusedIndex = idx;
    rows[idx].classList.add("focused");
    rows[idx].scrollIntoView({ block: "nearest" });
  }

  function toggleFocusedRow() {
    var rows = getVisibleRows();
    if (focusedIndex < 0 || focusedIndex >= rows.length) return;
    var row = rows[focusedIndex];
    row.click();
  }

  function collapseCurrent() {
    var open = document.querySelector(".expanded-post.open");
    if (open) {
      open.classList.remove("open");
      var row = open.previousElementSibling;
      if (row && row.classList.contains("row")) {
        row.classList.remove("expanded");
      }
    }
  }

  function starFocused() {
    var rows = getVisibleRows();
    if (focusedIndex < 0 || focusedIndex >= rows.length) return;
    var row = rows[focusedIndex];
    var slug = row.dataset.slug;
    var pid = parseInt(row.dataset.postId, 10);
    toggleStar(slug, pid);
    updateStarButtons(slug, pid);
    updateAllUI();
  }

  function findNextUnread(direction) {
    var rows = getVisibleRows();
    if (rows.length === 0) return;
    var start = focusedIndex < 0 ? 0 : focusedIndex + direction;
    var i = start;
    while (i >= 0 && i < rows.length) {
      if (!rows[i].classList.contains("read")) {
        setFocus(i);
        return;
      }
      i += direction;
    }
  }

  document.addEventListener("keydown", function(e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea") return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    var rows = getVisibleRows();
    switch (e.key) {
      case "j":
        e.preventDefault();
        setFocus(Math.min(focusedIndex + 1, rows.length - 1));
        break;
      case "k":
        e.preventDefault();
        setFocus(Math.max(focusedIndex - 1, 0));
        break;
      case "n":
        e.preventDefault();
        findNextUnread(1);
        break;
      case "p":
        e.preventDefault();
        findNextUnread(-1);
        break;
      case "Enter":
      case "o":
        e.preventDefault();
        toggleFocusedRow();
        break;
      case "Escape":
        e.preventDefault();
        collapseCurrent();
        break;
      case "s":
        e.preventDefault();
        starFocused();
        break;
      case "/":
        e.preventDefault();
        if (searchInput) searchInput.focus();
        break;
    }
  });
```

**Step 3: Reset focus on view switch**

In the `switchView` function, after the line `mainEl.scrollTop = 0;` (line 357), add:

```javascript
    focusedIndex = -1;
    var prev = document.querySelector(".row.focused");
    if (prev) prev.classList.remove("focused");
```

**Step 4: Rebuild and verify**

Run: `python3 scripts/build_reader.py`

Expected: Builds successfully. Open reader in browser:
- Press `j` — first row gets accent left border, scrolls into view
- Press `j` again — moves to next row
- Press `k` — moves back
- Press `Enter` — expands the focused row
- Press `Esc` — collapses it
- Press `s` — toggles star
- Press `/` — search input gets focus
- Press `n` — jumps to next unread post
- Press `p` — jumps to previous unread post

**Step 5: Commit**

```bash
git add scripts/static/reader.js scripts/static/reader.css
git commit -m "feat(reader): add keyboard navigation (j/k/n/p/Enter/o/Esc/s//)"
```

---

### Task 6: Final build and verification

**Step 1: Full rebuild**

```bash
python3 scripts/build_reader.py
```

**Step 2: Verify all features**

Open `reader/index.html` in browser:

1. **Keyboard nav:** j/k moves focus, Enter expands, Esc collapses, s stars, / focuses search, n/p jump to unread
2. **Mobile toolbar:** Resize to <767px — only hamburger, search, mark-all, theme visible
3. **Empty states:** Search gibberish — "Ничего не найдено" appears. Click starred with nothing starred — "Нет избранных постов"
4. **Fallback titles:** If any text-less posts exist, they show [Фото]/[Видео] in italics
5. **Full search:** Search for text that appears after 300 chars in a post — should find it

**Step 3: Commit if any fixes needed, then push**

```bash
git push origin main
```
