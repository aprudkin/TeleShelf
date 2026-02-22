(function() {
  "use strict";

  // ── Data ──
  var CHANNELS = JSON.parse(document.getElementById("channels-data").textContent);
  var channelSlugs = Object.keys(CHANNELS);
  var activeView = ""; // "latest" or channel slug

  // ── Per-channel state ──
  var states = {};
  var readSets = {};

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
  var btnStarred = document.getElementById("btn-starred");
  var starFilterActive = false;

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
    var feedView = (view === "starred") ? "latest" : view;

    // Update sidebar active
    document.querySelectorAll(".channel-item").forEach(function(el) {
      el.classList.toggle("active", el.dataset.view === view);
    });

    // Show/hide feed lists
    document.querySelectorAll(".feed-list").forEach(function(el) {
      el.style.display = (el.dataset.view === feedView) ? "" : "none";
    });

    // Collapse all expanded posts
    document.querySelectorAll(".expanded-post.open").forEach(function(el) {
      el.classList.remove("open");
    });
    document.querySelectorAll(".row.expanded").forEach(function(el) {
      el.classList.remove("expanded");
    });

    // Update tag select options for this view
    updateTagSelect(feedView);

    // Clear search
    if (searchInput) searchInput.value = "";
    clearSearchFilter();

    // Clear tag filter
    clearTagFilter();

    // Clear star filter, then activate if starred view
    clearStarFilter();
    if (view === "starred") {
      starFilterActive = true;
      applyStarFilter();
    }

    // Scroll to top
    mainEl.scrollTop = 0;

    try { localStorage.setItem("reader-active-view", view); } catch(e) {}

    updateAllUI();
  }

  // ── Row click → accordion ──
  function setupRowClicks() {
    document.querySelectorAll(".row").forEach(function(row) {
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
          var dot = row.querySelector(".new-dot");
          if (dot) dot.classList.remove("visible");
          updateAllUI();
        }
      });
    });
  }

  // ── Search ──
  function applySearchFilter() {
    var query = (searchInput.value || "").toLowerCase().trim();
    var feedView = (activeView === "starred") ? "latest" : activeView;
    var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
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

    tagSelect.innerHTML = '<option value="">\u0412\u0441\u0435 \u0442\u0435\u0433\u0438</option>';
    sorted.forEach(function(tag) {
      var opt = document.createElement("option");
      opt.value = tag;
      opt.textContent = tag + " (" + tagCounts[tag] + ")";
      tagSelect.appendChild(opt);
    });
  }

  function applyTagFilter() {
    var tag = tagSelect ? tagSelect.value : "";
    var feedView = (activeView === "starred") ? "latest" : activeView;
    var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
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

  // ── Star filtering ──
  function applyStarFilter() {
    var feedView = (activeView === "starred") ? "latest" : activeView;
    var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
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

  // ── Star toggle button ──
  if (btnStarred) {
    btnStarred.addEventListener("click", function() {
      starFilterActive = !starFilterActive;
      applyStarFilter();
    });
  }

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
      var feedView = (view === "starred") ? "latest" : view;
      var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
      if (!list) return;

      list.querySelectorAll(".row").forEach(function(row) {
        var slug = row.dataset.slug;
        var pid = parseInt(row.dataset.postId, 10);
        markRead(slug, pid);
      });

      if (view === "latest" || view === "starred") {
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
    document.querySelectorAll(".row").forEach(function(row) {
      var slug = row.dataset.slug;
      var pid = parseInt(row.dataset.postId, 10);
      row.classList.toggle("read", isRead(slug, pid));
      var dot = row.querySelector(".new-dot");
      if (dot) dot.classList.toggle("visible", isNewPost(slug, pid));
      var starBtn = row.querySelector(".star-btn");
      if (starBtn) {
        var starred = isStarred(slug, pid);
        starBtn.classList.toggle("starred", starred);
        starBtn.innerHTML = starred ? "&#9733;" : "&#9734;";
      }
    });

    document.querySelectorAll(".channel-item").forEach(function(item) {
      var view = item.dataset.view;
      var countEl = item.querySelector(".channel-count");
      if (!countEl) return;
      var unread = 0;

      if (view === "starred") {
        var starCount = Object.keys(starredSet).length;
        countEl.textContent = starCount > 0 ? starCount : "";
        return;
      } else if (view === "latest") {
        channelSlugs.forEach(function(slug) {
          unread += countUnread(slug);
        });
      } else if (CHANNELS[view]) {
        unread = countUnread(view);
      }
      countEl.textContent = unread > 0 ? unread : "";
    });

    if (counterEl) {
      var feedView = (activeView === "starred") ? "latest" : activeView;
      var list = document.querySelector('.feed-list[data-view="' + feedView + '"]');
      if (list) {
        var rows = list.querySelectorAll(".row");
        var total = 0, readCount = 0;
        rows.forEach(function(r) {
          if (!r.classList.contains("hidden-by-tag") && !r.classList.contains("hidden-by-search") && !r.classList.contains("hidden-by-star")) {
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
  if (savedView !== "latest" && savedView !== "starred" && channelSlugs.indexOf(savedView) === -1) {
    savedView = "latest";
  }
  switchView(savedView);
})();
