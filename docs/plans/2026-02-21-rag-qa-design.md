# RAG Q&A for Telegram Archive

**Date:** 2026-02-21
**Status:** Approved

## Goal

Add AI-powered Q&A to the TeleShelf reader: ask natural language questions about the archive and get LLM-generated answers with references to specific posts.

## Requirements

- Fully offline: Ollama for LLM + local embeddings + local vector store
- Q&A interface in reader/index.html
- Python backend (FastAPI) launched via `task serve`
- Incremental indexing integrated with `task sync`
- Russian language support

## Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Embeddings | Ollama `nomic-embed-text` | 768d, good multilingual, ~275MB model |
| LLM | Ollama `gemma2:9b` or `llama3.2:8b` | Configurable in config.py |
| Vector store | ChromaDB | SQLite-backed, local persistence, metadata filters |
| Backend | FastAPI + uvicorn | Serves reader + /api/ask endpoint |
| HTTP client | httpx | For Ollama API calls |

## Architecture

### File structure

```
scripts/
  rag/
    __init__.py
    indexer.py       # Index posts → ChromaDB
    searcher.py      # Search + generate answer
    server.py        # FastAPI: /api/ask + serve reader
    config.py        # Models, top-K, paths
data/
  chromadb/          # Persistent ChromaDB storage (gitignored)
```

### Data flow

```
[task index]
  all-messages.json → Ollama nomic-embed-text → ChromaDB (data/chromadb/)

[task serve]  (starts server.py)
  GET /           → reader/index.html
  POST /api/ask   → { question, channel?, tags? }
                  → ChromaDB similarity search (top-K posts)
                  → Ollama LLM (question + contexts)
                  → SSE stream: { answer, sources }
```

## Indexing (indexer.py)

### What gets indexed
- Post text (primary search content)
- Metadata: `channel_slug`, `channel_name`, `post_id`, `date`, `tags[]`, `has_media`, `has_thread`

### Chunking
One post = one document. Telegram posts are short (up to 4096 chars), no splitting needed.

### Incremental indexing
1. Read `all-messages.json` for channel
2. Query ChromaDB for already-indexed post IDs for this channel
3. Compute diff — new posts only
4. Batch embed (50 at a time) via Ollama and add to ChromaDB

### Empty posts
Posts without text (media-only) are skipped.

## Search & Generation (searcher.py)

### Query pipeline
1. Embed question via Ollama `nomic-embed-text`
2. ChromaDB similarity search (top-K=10, optional channel/tag filters)
3. Build LLM prompt with retrieved posts as context
4. Ollama generates answer (streaming via SSE)
5. Parse source references [1], [2]... → map to post_id/channel
6. Return: `{ answer, sources: [{post_id, channel_slug, channel_name, snippet, date}] }`

### System prompt
```
You are an assistant for a Telegram channel archive.
Answer the question using ONLY the provided posts.
For each claim, cite the source as [number].
If the information is insufficient, say so.
Answer in the same language as the question.
```

### Filters
API accepts optional `channel` and `tags[]` — passed as ChromaDB `where` filters.
When a channel is selected in the reader, searches are scoped to that channel.

## Reader UI Changes

### Two operating modes
1. **Offline** (opened as file): regular text search, Q&A unavailable (hint: "Run `task serve` for AI search")
2. **Via server** (`task serve`): full Q&A + regular search

### Q&A panel
- Search input in toolbar doubles as Q&A input when server is available
- Answer appears in a slide-down panel above the post list
- Source links are clickable — scroll to and expand the referenced post
- Answer streams in real-time (SSE)
- Enter key submits the question
- Channel/tag filters apply to RAG search too

## Task Commands

| Command | Description |
|---------|-------------|
| `task rag-setup` | Install Python deps + pull Ollama models |
| `task index` | Index all channels incrementally |
| `task index -- <slug>` | Index one channel |
| `task serve` | Start FastAPI server (reader + API) on localhost:8080 |

### Integration with `task sync`
After tagging step, call `python3 scripts/rag/indexer.py --channel $SLUG` to index new posts.
If Ollama is unavailable — skip with warning (same pattern as tagging).

## Dependencies

### Python (added to existing jinja2)
- `chromadb`
- `fastapi`
- `uvicorn`
- `httpx`

### External
- Ollama (`brew install ollama`)
- Models: `ollama pull nomic-embed-text`, `ollama pull gemma2:9b`

## Gitignore additions
- `data/chromadb/`
