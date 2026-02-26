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
        parts.append(f'<div class="thread-text">{format_text(text, msg.get("entities"))}</div>')
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
    messages.sort(key=lambda m: m["id"], reverse=True)

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
        "text_html": format_text(text, msg.get("entities")),
        "media_html": get_media_html(media_base, channel_id, pid, file_field),
        "media_icon_class": media_icon_class(file_field),
        "tags": post_tags,
        "tags_str": ",".join(post_tags),
        "search_text": escape(text.replace("\n", " ")),
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
        saved_state_json=saved_state_json,
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
