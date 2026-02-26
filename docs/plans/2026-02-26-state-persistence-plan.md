# State Persistence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add file-based state persistence to the TeleShelf reader via build-time embedding and Export/Import buttons.

**Architecture:** Keep localStorage as primary runtime store. Add a `<script id="saved-state">` block embedded at build time from `reader/state.json`. On load, merge embedded + localStorage (union strategy). Export/Import buttons allow manual state file management.

**Tech Stack:** Vanilla JS (existing reader.js), Python (existing build_reader.py), Jinja2 templates

**Design doc:** `docs/plans/2026-02-26-state-persistence-design.md`

---

### Task 1: Add saved-state script block to HTML template

**Files:**
- Modify: `scripts/templates/reader.html:14-16` (after channels-data script block)

**Step 1: Add the conditional saved-state block**

In `scripts/templates/reader.html`, after the existing `<script id="channels-data">` block (line 16), add:

```html
{% if saved_state_json %}
<script id="saved-state" type="application/json">
{{ saved_state_json }}
</script>
{% endif %}
```

The full section should read:

```html
<script id="channels-data" type="application/json">
{{ channels_json }}
</script>

{% if saved_state_json %}
<script id="saved-state" type="application/json">
{{ saved_state_json }}
</script>
{% endif %}
```

**Step 2: Verify template renders without saved state**

Run: `cd /Users/alexeyprudkin/dev/teleshelf && python3 scripts/build_reader.py`

Expected: Builds successfully without errors. The `<script id="saved-state">` block should NOT appear in `reader/index.html` (since no `reader/state.json` exists yet).

Verify: `grep 'saved-state' reader/index.html` — should return nothing.

**Step 3: Commit**

```bash
git add scripts/templates/reader.html
git commit -m "feat(reader): add conditional saved-state script block to template"
```

---

### Task 2: Modify build_reader.py to read and embed state.json

**Files:**
- Modify: `scripts/build_reader.py:353-458` (in `build_combined_reader` function)

**Step 1: Add state file reading logic**

In `build_combined_reader()`, after the `channels_js_data` dict is built (around line 421) and before loading CSS/JS, add:

```python
    # Load saved state if present
    saved_state_json = ""
    state_path = os.path.join("reader", "state.json")
    if os.path.isfile(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            saved_state_raw = f.read()
        # Validate it's valid JSON
        try:
            json.loads(saved_state_raw)
            saved_state_json = saved_state_raw
            print(f"  Embedded saved state from {state_path}")
        except json.JSONDecodeError:
            print(f"  Warning: {state_path} is not valid JSON, skipping", file=sys.stderr)
```

**Step 2: Pass saved_state_json to template render**

Modify the `template.render()` call (line 439) to include the new variable:

```python
    html_output = template.render(
        css=css,
        js=js,
        channels=channels_data,
        all_posts=all_posts,
        all_tags=all_tags,
        channels_json=json.dumps(channels_js_data, ensure_ascii=False),
        saved_state_json=saved_state_json,
    )
```

**Step 3: Verify with a test state file**

Create a temporary test file:

```bash
mkdir -p reader
echo '{"version":1,"channels":{},"starred":{},"preferences":{}}' > reader/state.json
python3 scripts/build_reader.py
grep 'saved-state' reader/index.html
```

Expected: `grep` finds the `<script id="saved-state">` block with the test JSON.

Then clean up: `rm reader/state.json`

**Step 4: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat(build): read reader/state.json and embed into HTML at build time"
```

---

### Task 3: Add merge logic to reader.js (on-load state initialization)

**Files:**
- Modify: `scripts/static/reader.js:1-83` (state initialization section)

**Step 1: Add a merge function and embedded state parsing**

After the `starKey` / `isStarred` / `toggleStar` / `updateStarButtons` functions (after line 49) and before `storageKey` (line 51), add a `loadSavedState` function and a merge helper:

```javascript
  // ── Saved state (embedded at build time) ──
  var savedState = null;
  (function() {
    try {
      var el = document.getElementById("saved-state");
      if (el) savedState = JSON.parse(el.textContent);
    } catch(e) {}
  })();

  function mergeSavedState() {
    if (!savedState || savedState.version !== 1) return;

    // Merge starred: union of both
    var savedStarred = savedState.starred || {};
    for (var key in savedStarred) {
      if (savedStarred[key] && !starredSet[key]) {
        starredSet[key] = true;
      }
    }
    try {
      localStorage.setItem("reader-starred", JSON.stringify(starredSet));
    } catch(e) {}

    // Merge per-channel state
    var savedChannels = savedState.channels || {};
    for (var slug in savedChannels) {
      if (!CHANNELS[slug]) continue;
      var saved = savedChannels[slug];
      var local = loadState(slug);

      if (!local) {
        // No local state — use saved state directly
        var st = {
          readPosts: saved.readPosts || [],
          lastSyncMaxId: saved.lastSyncMaxId || 0
        };
        try {
          localStorage.setItem(storageKey(slug), JSON.stringify(st));
        } catch(e) {}
        continue;
      }

      // Merge readPosts: set union
      var readSet = {};
      var i;
      for (i = 0; i < local.readPosts.length; i++) {
        readSet[local.readPosts[i]] = true;
      }
      var savedPosts = saved.readPosts || [];
      for (i = 0; i < savedPosts.length; i++) {
        readSet[savedPosts[i]] = true;
      }
      local.readPosts = Object.keys(readSet).map(Number);

      // lastSyncMaxId: take max
      if (saved.lastSyncMaxId > local.lastSyncMaxId) {
        local.lastSyncMaxId = saved.lastSyncMaxId;
      }

      try {
        localStorage.setItem(storageKey(slug), JSON.stringify(local));
      } catch(e) {}
    }

    // Preferences: localStorage wins (don't overwrite)
    var prefs = savedState.preferences || {};
    try {
      if (!localStorage.getItem("reader-theme") && prefs.theme) {
        localStorage.setItem("reader-theme", prefs.theme);
      }
      if (!localStorage.getItem("reader-active-view") && prefs.activeView) {
        localStorage.setItem("reader-active-view", prefs.activeView);
      }
    } catch(e) {}
  }
```

**Step 2: Call mergeSavedState before existing init**

Right before the `// Init states` block (currently line 69), call:

```javascript
  mergeSavedState();
```

This ensures the merge happens before `loadState()` reads from localStorage in the init loop.

**Step 3: Verify build succeeds**

Run: `python3 scripts/build_reader.py`

Expected: Builds without errors.

**Step 4: Commit**

```bash
git add scripts/static/reader.js
git commit -m "feat(reader): merge embedded saved state into localStorage on load"
```

---

### Task 4: Add Export function to reader.js

**Files:**
- Modify: `scripts/static/reader.js` (add after the `mergeSavedState` function)

**Step 1: Add exportState function**

After the `mergeSavedState` function, add:

```javascript
  // ── Export / Import ──
  function exportState() {
    var data = {
      version: 1,
      exportedAt: new Date().toISOString(),
      channels: {},
      starred: JSON.parse(JSON.stringify(starredSet)),
      preferences: {}
    };

    channelSlugs.forEach(function(slug) {
      var st = loadState(slug);
      if (st) {
        data.channels[slug] = {
          readPosts: st.readPosts || [],
          lastSyncMaxId: st.lastSyncMaxId || 0
        };
      }
    });

    try { data.preferences.theme = localStorage.getItem("reader-theme") || "dark"; } catch(e) {}
    try { data.preferences.activeView = localStorage.getItem("reader-active-view") || "latest"; } catch(e) {}

    var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "state.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
```

**Step 2: Commit**

```bash
git add scripts/static/reader.js
git commit -m "feat(reader): add exportState function for downloading state.json"
```

---

### Task 5: Add Import function to reader.js

**Files:**
- Modify: `scripts/static/reader.js` (add after `exportState`)

**Step 1: Add importState function**

After `exportState`, add:

```javascript
  function importState() {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.addEventListener("change", function() {
      var file = input.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function() {
        try {
          var data = JSON.parse(reader.result);
          if (data.version !== 1) {
            alert("Unsupported state file version");
            return;
          }

          // Merge starred
          var importedStarred = data.starred || {};
          for (var key in importedStarred) {
            if (importedStarred[key]) starredSet[key] = true;
          }
          try {
            localStorage.setItem("reader-starred", JSON.stringify(starredSet));
          } catch(e) {}

          // Merge per-channel
          var importedChannels = data.channels || {};
          for (var slug in importedChannels) {
            if (!CHANNELS[slug]) continue;
            var imported = importedChannels[slug];
            var local = loadState(slug) || { readPosts: [], lastSyncMaxId: 0 };

            var readSet = {};
            var i;
            for (i = 0; i < local.readPosts.length; i++) {
              readSet[local.readPosts[i]] = true;
            }
            var importedPosts = imported.readPosts || [];
            for (i = 0; i < importedPosts.length; i++) {
              readSet[importedPosts[i]] = true;
            }
            local.readPosts = Object.keys(readSet).map(Number);
            if (imported.lastSyncMaxId > local.lastSyncMaxId) {
              local.lastSyncMaxId = imported.lastSyncMaxId;
            }

            states[slug] = local;
            // Rebuild readSets
            var rs = {};
            for (i = 0; i < local.readPosts.length; i++) {
              rs[local.readPosts[i]] = true;
            }
            readSets[slug] = rs;

            saveState(slug);
          }

          // Preferences: imported values only if localStorage empty
          var prefs = data.preferences || {};
          try {
            if (!localStorage.getItem("reader-theme") && prefs.theme) {
              localStorage.setItem("reader-theme", prefs.theme);
            }
          } catch(e) {}

          updateAllUI();
        } catch(e) {
          alert("Invalid state file: " + e.message);
        }
      };
      reader.readAsText(file);
    });
    input.click();
  }
```

**Step 2: Commit**

```bash
git add scripts/static/reader.js
git commit -m "feat(reader): add importState function for loading state from file"
```

---

### Task 6: Add Export/Import buttons to toolbar (template + CSS + event wiring)

**Files:**
- Modify: `scripts/templates/reader.html:58-69` (toolbar section)
- Modify: `scripts/static/reader.css` (button styles)
- Modify: `scripts/static/reader.js` (event listeners at bottom)

**Step 1: Add buttons to toolbar template**

In `scripts/templates/reader.html`, in the toolbar section, add Export and Import buttons next to the theme toggle. Insert before the closing `</header>` (line 69):

Replace the toolbar section (lines 58-69) with:

```html
<header class="toolbar">
  <button id="hamburger" class="hamburger" aria-label="Menu">&#9776;</button>
  <input id="search-input" class="toolbar-search" type="text" placeholder="Поиск...">
  <select id="tag-select" class="toolbar-tag-select">
    <option value="">Все теги</option>
  </select>
  <button id="btn-starred" class="toolbar-btn" aria-label="Show starred only">&#9733; Starred</button>
  <span class="toolbar-spacer"></span>
  <span id="counter" class="toolbar-counter"></span>
  <button id="btn-mark-all" class="toolbar-btn">Прочитать все</button>
  <button id="btn-export" class="toolbar-btn toolbar-btn-icon" aria-label="Export state" title="Экспорт состояния">&#8681;</button>
  <button id="btn-import" class="toolbar-btn toolbar-btn-icon" aria-label="Import state" title="Импорт состояния">&#8679;</button>
  <button id="theme-toggle" class="theme-toggle" aria-label="Toggle theme"></button>
</header>
```

**Step 2: Add icon button styles to CSS**

In `scripts/static/reader.css`, after the `.toolbar-btn.active` rule (line 95), add:

```css
.toolbar-btn-icon {
  font-size: 16px;
  padding: 2px 6px;
  line-height: 1;
}
```

**Step 3: Wire up button event listeners in JS**

In `scripts/static/reader.js`, in the `// ── Init ──` section (around line 528), after `setupRowClicks();`, add:

```javascript
  var btnExport = document.getElementById("btn-export");
  var btnImport = document.getElementById("btn-import");
  if (btnExport) btnExport.addEventListener("click", exportState);
  if (btnImport) btnImport.addEventListener("click", importState);
```

**Step 4: Build and verify**

Run: `python3 scripts/build_reader.py`

Expected: Builds successfully. Open `reader/index.html` in browser. Verify:
- Export and Import buttons visible in toolbar (down-arrow and up-arrow icons)
- Clicking Export downloads a `state.json` file
- Clicking Import opens file picker
- Importing the exported file works without errors

**Step 5: Commit**

```bash
git add scripts/templates/reader.html scripts/static/reader.css scripts/static/reader.js
git commit -m "feat(reader): add Export/Import buttons to toolbar for state persistence"
```

---

### Task 7: Verify full round-trip

**Step 1: Build the reader**

```bash
python3 scripts/build_reader.py
```

**Step 2: Open reader, create some state**

Open `reader/index.html` in browser. Click a few posts (mark as read), star a few. Click Export — save `state.json` to `reader/state.json`.

**Step 3: Rebuild with embedded state**

```bash
python3 scripts/build_reader.py
```

Expected output includes: `Embedded saved state from reader/state.json`

**Step 4: Clear browser localStorage and reload**

In browser devtools: `localStorage.clear()`, then reload the page.

Expected: Previously read/starred posts should still appear read/starred (restored from embedded state).

**Step 5: Verify import works independently**

Clear localStorage again. Click Import, select the same `state.json`. Expected: state restored without rebuild.

**Step 6: Clean up test state file**

```bash
rm reader/state.json
```
