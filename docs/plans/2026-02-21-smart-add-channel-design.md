# Smart add-channel Command

## Goal

Allow `task add-channel` to accept just a URL and auto-derive the slug from the Telegram channel username, with interactive confirmation.

## New Syntax

```bash
# Public channel — slug auto-derived, user confirms interactively
task add-channel -- "https://t.me/seeallochnaya/3412"
# Prompts: "Suggested slug: seeallochnaya. Press Enter to confirm or type a custom slug:"

# Private channel — slug required (no username in URL)
task add-channel -- my-slug "https://t.me/c/1234567890/154"
```

## Behavior

### Argument detection

- **1 arg (URL):** parse URL. If public, derive slug from username and prompt for confirmation. If private, error with usage hint.
- **2 args (slug + URL):** use explicit slug (for private URLs).

### Interactive prompt

When slug is auto-derived from a public URL:
```
Suggested slug: seeallochnaya. Press Enter to confirm or type a custom slug:
```
- Empty input = accept suggested slug
- Non-empty input = use as custom slug (validated with existing `^[a-zA-Z0-9_-]+$` check)

### Private URL handling

Private URLs (`t.me/c/<id>/<post>`) have no username, so slug cannot be derived. When only a private URL is provided:
```
Error: Private URLs require an explicit slug.
Usage: task add-channel -- <slug> "https://t.me/c/<id>/<post>"
```

## Changes Required

1. **Taskfile.yml `add-channel` task** (lines 32-44):
   - Replace 2-arg parsing with smart detection
   - Add URL-detection logic to distinguish "1 URL arg" from "2 slug+URL args"
   - Add `read` prompt for slug confirmation on public URLs
   - Update help text and examples

2. **CLAUDE.md**: Update `add-channel` usage examples to show new syntax
