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
