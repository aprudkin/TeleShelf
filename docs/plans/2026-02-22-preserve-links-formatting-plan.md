# Preserve Links & Formatting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Recover lost links and blockquotes from Telegram posts by using `tdl --raw` export and entity-based HTML rendering.

**Architecture:** Create a standalone `scripts/extract_entities.py` that processes raw tdl exports (extracts entities, converts UTF-16 offsets, strips `raw` field). Rewrite `format_text()` in `build_reader.py` to render entities as HTML. Add `--raw` to tdl export in the sync pipeline, and a `re-export` task for existing channels.

**Tech Stack:** Python 3, tdl CLI, Jinja2 (existing)

---

### Task 1: Create `scripts/extract_entities.py`

**Files:**
- Create: `scripts/extract_entities.py`

This is a standalone script and importable module. When run as `python3 scripts/extract_entities.py input.json output.json`, it processes a raw tdl export file: extracts entities from `raw.Entities`, converts UTF-16 offsets to Python string indices, detects entity types, adds `entities` array to each message, removes the `raw` field, and writes the result.

**Step 1: Write `scripts/extract_entities.py`**

```python
#!/usr/bin/env python3
"""
extract_entities.py — Extract Telegram entities from raw tdl export.

Usage:
    python3 scripts/extract_entities.py input.json [output.json]

If output.json is omitted, overwrites input.json in place.

For each message with raw.Entities, extracts normalized entities
(text_link, blockquote, url, mention, hashtag, custom_emoji, unknown),
converts UTF-16 offsets to Python string indices, and removes the raw field.
"""

import json
import re
import sys


def utf16_to_python(text: str, utf16_offset: int, utf16_length: int) -> tuple[int, int]:
    """Convert UTF-16 code unit offset/length to Python string indices."""
    encoded = text.encode("utf-16-le")
    byte_offset = utf16_offset * 2
    byte_length = utf16_length * 2
    prefix = encoded[:byte_offset].decode("utf-16-le")
    entity_text = encoded[byte_offset:byte_offset + byte_length].decode("utf-16-le")
    return len(prefix), len(entity_text)


def classify_entity(raw_ent: dict, text: str, py_offset: int, py_length: int) -> dict:
    """Detect entity type from raw MTProto fields and text heuristics."""
    entity = {"offset": py_offset, "length": py_length}

    if raw_ent.get("URL"):
        entity["type"] = "text_link"
        entity["url"] = raw_ent["URL"]
    elif "Collapsed" in raw_ent:
        entity["type"] = "blockquote"
    elif raw_ent.get("DocumentID"):
        entity["type"] = "custom_emoji"
    else:
        ent_text = text[py_offset:py_offset + py_length]
        if re.match(r'^https?://', ent_text):
            entity["type"] = "url"
        elif re.match(r'^@\w', ent_text):
            entity["type"] = "mention"
        elif re.match(r'^#', ent_text):
            entity["type"] = "hashtag"
        else:
            entity["type"] = "unknown"

    return entity


def extract_entities(message: dict) -> list:
    """Extract normalized entities from a single raw message."""
    raw = message.get("raw")
    if not raw:
        return []

    raw_entities = raw.get("Entities")
    if not raw_entities:
        return []

    text = message.get("text", "") or raw.get("Message", "")
    if not text:
        return []

    entities = []
    for raw_ent in raw_entities:
        utf16_offset = raw_ent.get("Offset", 0)
        utf16_length = raw_ent.get("Length", 0)
        if utf16_length <= 0:
            continue

        try:
            py_offset, py_length = utf16_to_python(text, utf16_offset, utf16_length)
        except (UnicodeDecodeError, ValueError):
            continue

        entity = classify_entity(raw_ent, text, py_offset, py_length)
        entities.append(entity)

    return entities


def process_file(input_path: str, output_path: str) -> None:
    """Process a raw tdl export file: extract entities, strip raw field."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    for msg in messages:
        entities = extract_entities(msg)
        if entities:
            msg["entities"] = entities
        msg.pop("raw", None)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Processed {len(messages)} message(s) in {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_entities.py input.json [output.json]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path
    process_file(input_path, output_path)
```

**Step 2: Verify it works on a raw export**

Run:
```bash
CHANNEL_ID=$(python3 -c "import json; print(json.load(open('downloads/ris-ai/channel.json'))['channel_id'])")
tdl chat export -c "$CHANNEL_ID" --all --with-content --raw -T id -i 575 -i 578 -o /tmp/raw-test.json
python3 scripts/extract_entities.py /tmp/raw-test.json /tmp/extracted-test.json
python3 -c "
import json
data = json.load(open('/tmp/extracted-test.json'))
for msg in data['messages']:
    print(f'ID: {msg[\"id\"]}')
    for e in msg.get('entities', []):
        print(f'  {e[\"type\"]}: offset={e[\"offset\"]} len={e[\"length\"]}', end='')
        if e.get('url'): print(f' url={e[\"url\"]}', end='')
        print()
    print()
"
```

Expected: Message 576 should show `text_link` entities with the sereja.tech URLs, `blockquote` entity, and `custom_emoji` entities. No `raw` field in the output.

**Step 3: Commit**

```bash
git add scripts/extract_entities.py
git commit -m "feat: add entity extraction from raw tdl exports

Closes #N"
```

---

### Task 2: Rewrite `format_text()` in `build_reader.py`

**Files:**
- Modify: `scripts/build_reader.py:68-84` (the `format_text` function)

Add an optional `entities` parameter. When entities are provided, use entity-based rendering (text_link → `<a>`, blockquote → `<blockquote>`, url → `<a>`, mention → `<a>`). When not provided, fall back to the existing bare-URL regex.

**Step 1: Add helper functions above `format_text`**

Insert at `build_reader.py:67` (before `format_text`):

```python
def _wrap_paragraphs(html_text: str) -> str:
    """Split on double newlines into <p> tags, single newlines to <br>."""
    paragraphs = re.split(r'\n{2,}', html_text)
    parts = []
    for p in paragraphs:
        p = p.strip()
        if p:
            inner = p.replace("\n", "<br>\n")
            parts.append(f"<p>{inner}</p>")
    return "\n".join(parts)


def _apply_inline_entities(text: str, entities: list) -> str:
    """Apply inline entities (text_link, url, mention) to text, returning HTML."""
    renderable = [e for e in entities if e["type"] in ("text_link", "url", "mention")]
    renderable.sort(key=lambda e: e["offset"])

    parts = []
    pos = 0
    for ent in renderable:
        offset = ent["offset"]
        length = ent["length"]
        if offset < pos:
            continue  # skip overlapping

        # Text before entity
        if offset > pos:
            parts.append(escape(text[pos:offset]))

        ent_text = text[offset:offset + length]
        if ent["type"] == "text_link":
            url = html.escape(ent["url"], quote=True)
            parts.append(f'<a href="{url}" target="_blank" rel="noopener noreferrer">{escape(ent_text)}</a>')
        elif ent["type"] == "url":
            parts.append(f'<a href="{escape(ent_text)}" target="_blank" rel="noopener noreferrer">{escape(ent_text)}</a>')
        elif ent["type"] == "mention":
            username = ent_text.lstrip("@")
            parts.append(f'<a href="https://t.me/{html.escape(username, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(ent_text)}</a>')

        pos = offset + length

    # Remaining text
    if pos < len(text):
        parts.append(escape(text[pos:]))

    return "".join(parts)
```

**Step 2: Rewrite `format_text` at line 68**

Replace the existing `format_text` function (lines 68-84) with:

```python
def format_text(text: str, entities: list | None = None) -> str:
    if not text:
        return ""

    # Fallback: no entities — use bare-URL regex (backwards compatible)
    if not entities:
        escaped = escape(text)
        escaped = re.sub(
            r'(https?://[^\s<>&]+)',
            r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
            escaped,
        )
        return _wrap_paragraphs(escaped)

    # Entity-based rendering
    blockquotes = [e for e in entities if e["type"] == "blockquote"]
    inline_ents = [e for e in entities if e["type"] in ("text_link", "url", "mention")]
    blockquotes.sort(key=lambda e: e["offset"])

    # Split text into regions: blockquote vs non-blockquote
    regions = []  # (is_blockquote, region_text, region_inline_entities)
    pos = 0

    for bq in blockquotes:
        bq_start = bq["offset"]
        bq_end = bq_start + bq["length"]

        if bq_start > pos:
            region_text = text[pos:bq_start]
            region_ents = [
                {**e, "offset": e["offset"] - pos}
                for e in inline_ents
                if e["offset"] >= pos and e["offset"] + e["length"] <= bq_start
            ]
            regions.append((False, region_text, region_ents))

        bq_text = text[bq_start:bq_end]
        bq_ents = [
            {**e, "offset": e["offset"] - bq_start}
            for e in inline_ents
            if e["offset"] >= bq_start and e["offset"] + e["length"] <= bq_end
        ]
        regions.append((True, bq_text, bq_ents))
        pos = bq_end

    if pos < len(text):
        region_text = text[pos:]
        region_ents = [
            {**e, "offset": e["offset"] - pos}
            for e in inline_ents
            if e["offset"] >= pos
        ]
        regions.append((False, region_text, region_ents))

    # Render each region
    html_parts = []
    for is_bq, region_text, region_ents in regions:
        inner = _apply_inline_entities(region_text, region_ents)
        wrapped = _wrap_paragraphs(inner)
        if is_bq:
            html_parts.append(f"<blockquote>{wrapped}</blockquote>")
        else:
            html_parts.append(wrapped)

    return "\n".join(html_parts)
```

**Step 3: Run `python3 scripts/build_reader.py` to verify it builds**

Run: `python3 scripts/build_reader.py`
Expected: builds without errors (all existing posts use the fallback path since they have no entities yet)

**Step 4: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: rewrite format_text with entity-based HTML rendering

Closes #N"
```

---

### Task 3: Pass entities through call sites

**Files:**
- Modify: `scripts/build_reader.py:243` (`prepare_post`)
- Modify: `scripts/build_reader.py:142` (`render_thread_message`)

**Step 1: Update `prepare_post` at line 243**

Change line 243 from:
```python
"text_html": format_text(text),
```
to:
```python
"text_html": format_text(text, msg.get("entities")),
```

**Step 2: Update `render_thread_message` at line 142**

Change line 142 from:
```python
parts.append(f'<div class="thread-text">{format_text(text)}</div>')
```
to:
```python
parts.append(f'<div class="thread-text">{format_text(text, msg.get("entities"))}</div>')
```

**Step 3: Verify build still works**

Run: `python3 scripts/build_reader.py`
Expected: builds without errors

**Step 4: Commit**

```bash
git add scripts/build_reader.py
git commit -m "feat: pass entities to format_text in prepare_post and render_thread_message

Closes #N"
```

---

### Task 4: Add blockquote CSS

**Files:**
- Modify: `scripts/static/reader.css`

**Step 1: Add blockquote styles**

Add to `reader.css` (after `.post-body` styles or at the end of the post-body section):

```css
.post-body blockquote {
  border-left: 3px solid var(--accent);
  padding: 4px 12px;
  margin: 8px 0;
  color: var(--text-muted);
}
```

**Step 2: Rebuild reader to verify**

Run: `python3 scripts/build_reader.py`
Expected: builds without errors

**Step 3: Commit**

```bash
git add scripts/static/reader.css
git commit -m "style: add blockquote styling for entity-based rendering

Closes #N"
```

---

### Task 5: Update Taskfile sync to use `--raw` and extract entities

**Files:**
- Modify: `Taskfile.yml:276` (export command)
- Modify: `Taskfile.yml:294-295` (add extraction step after export, before merge)

**Step 1: Add `--raw` to export command**

Change line 276 from:
```bash
tdl chat export -c "$CHANNEL_ID" --all --with-content -T id -i "$NEXT_ID" -i 999999 -o "$TEMP_FILE"
```
to:
```bash
tdl chat export -c "$CHANNEL_ID" --all --with-content --raw -T id -i "$NEXT_ID" -i 999999 -o "$TEMP_FILE"
```

**Step 2: Add entity extraction step**

Insert after the "Found N new message(s)" echo (after line 294, before the merge comment at line 296):

```bash
      # Extract entities from raw export
      echo "Extracting entities..."
      python3 "{{.INSTALL_DIR}}/scripts/extract_entities.py" "$TEMP_FILE"
```

**Step 3: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: use --raw tdl export and extract entities during sync

Closes #N"
```

---

### Task 6: Add `re-export` and `re-export-all` tasks

**Files:**
- Modify: `Taskfile.yml` (add new tasks after `sync-all`)

**Step 1: Add `re-export` task**

Insert after the `sync-all` task (before `build-reader`):

```yaml
  re-export:
    desc: Re-export all messages with entities for a channel
    summary: |
      Usage: task re-export -- <slug>

      Re-exports all messages from a channel with --raw flag to recover
      entity data (links, blockquotes). Updates existing all-messages.json
      by merging entity data into existing messages.
    preconditions:
      - sh: '[ -n "{{.CLI_ARGS}}" ]'
        msg: "Error: slug is required. Usage: task re-export -- <slug>"
      - sh: '[ -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel.json" ]'
        msg: "Error: channel.json not found"
      - sh: '[ -f "{{.DOWNLOADS_DIR}}/{{.CLI_ARGS}}/channel-full/all-messages.json" ]'
        msg: "Error: all-messages.json not found"
    silent: true
    cmd: |
      set -eo pipefail

      SLUG="{{.CLI_ARGS}}"
      CHANNEL_DIR="{{.DOWNLOADS_DIR}}/$SLUG"
      CONFIG_FILE="$CHANNEL_DIR/channel.json"
      MESSAGES_FILE="$CHANNEL_DIR/channel-full/all-messages.json"
      TEMP_FILE="/tmp/teleshelf-reexport-$SLUG.json"

      CHANNEL_ID=$(python3 -c "import json, sys; print(json.load(open(sys.argv[1]))['channel_id'])" "$CONFIG_FILE")
      echo "Re-exporting: $SLUG (ID: $CHANNEL_ID)"

      # Export ALL messages with --raw
      echo "Exporting all messages with --raw..."
      tdl chat export -c "$CHANNEL_ID" --all --with-content --raw -T id -i 1 -i 999999 -o "$TEMP_FILE"

      # Extract entities
      echo "Extracting entities..."
      python3 "{{.INSTALL_DIR}}/scripts/extract_entities.py" "$TEMP_FILE"

      # Merge entities into existing messages (update existing, add new)
      python3 -c "
      import json, sys

      with open(sys.argv[1]) as f:
          new_data = json.load(f)
      new_msgs = {m['id']: m for m in new_data.get('messages', [])}

      with open(sys.argv[2]) as f:
          existing_data = json.load(f)
      existing_msgs = existing_data.get('messages', [])

      # Update existing messages with entities from re-export
      updated = 0
      for msg in existing_msgs:
          if msg['id'] in new_msgs:
              new_msg = new_msgs[msg['id']]
              if 'entities' in new_msg:
                  msg['entities'] = new_msg['entities']
                  updated += 1

      existing_data['messages'] = existing_msgs
      with open(sys.argv[2], 'w') as f:
          json.dump(existing_data, f, indent=2, ensure_ascii=False)
          f.write('\n')

      print(f'Updated entities for {updated} message(s).')
      " "$TEMP_FILE" "$MESSAGES_FILE"

      rm -f "$TEMP_FILE"
      echo "Re-export complete for '$SLUG'."

  re-export-all:
    desc: Re-export all channels with entities
    summary: |
      Usage: task re-export-all

      Re-exports all channels to recover entity data (links, blockquotes).
      Builds reader once at the end.
    silent: true
    cmd: |
      set -o pipefail

      SUCCEEDED=0
      FAILED=0
      FAILED_SLUGS=""

      for CONFIG in "{{.DOWNLOADS_DIR}}"/*/channel.json; do
        [[ -f "$CONFIG" ]] || continue
        SLUG="$(basename "$(dirname "$CONFIG")")"
        echo "========================================="
        echo "Re-exporting: $SLUG"
        echo "========================================="
        if task re-export -- "$SLUG"; then
          SUCCEEDED=$((SUCCEEDED + 1))
        else
          FAILED=$((FAILED + 1))
          FAILED_SLUGS="$FAILED_SLUGS $SLUG"
        fi
        echo ""
      done

      echo "========================================="
      echo "Building reader..."
      echo "========================================="
      python3 "{{.INSTALL_DIR}}/scripts/build_reader.py"

      echo ""
      echo "========================================="
      echo "Re-export complete: $SUCCEEDED succeeded, $FAILED failed."
      if [[ -n "$FAILED_SLUGS" ]]; then
        echo "Failed channels:$FAILED_SLUGS"
      fi
      echo "  open {{.ROOT_DIR}}/reader/index.html"
      echo "========================================="
```

**Step 2: Commit**

```bash
git add Taskfile.yml
git commit -m "feat: add re-export and re-export-all tasks for entity recovery

Closes #N"
```

---

### Task 7: Run re-export and verify

**Step 1: Re-export all channels**

Run: `task re-export-all`
Expected: all channels re-exported with entities, reader rebuilt

**Step 2: Verify message 576 has clickable links**

Open `reader/index.html`, find post 576 in ris-ai channel, expand it. Verify:
- "Персонал Корп у" is a clickable link to `https://sereja.tech/blog/personal-corporation-event-driven-agents/`
- "эту ссылку" is a clickable link to `https://sereja.tech/blog/github-projects-ai-agent-memory`
- The blockquote ("Внимание вопрос: ...") is styled as a blockquote

**Step 3: Spot-check other channels**

Expand a few posts in other channels that are known to have links. Verify links are clickable.

**Step 4: Commit updated data files (if desired)**

The `all-messages.json` files now contain `entities` arrays. These are in `downloads/` which may or may not be gitignored — commit if tracked.

**Step 5: Final commit**

```bash
git commit -m "chore: re-export all channels with entity data"
```
