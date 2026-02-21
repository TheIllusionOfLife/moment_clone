# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend
uv sync
uv run uvicorn backend.main:app --reload

# Database (Supabase locally)
supabase start
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Seed data
uv run python -m backend.scripts.seed_dishes
uv run python -m backend.scripts.seed_knowledge_base   # embeds principles → pgvector

# Frontend
cd frontend && bun install
cd frontend && bun dev

# Tests
uv run pytest
uv run pytest backend/
uv run pytest pipeline/ -m integration   # requires GEMINI_API_KEY

# Backend lint/format
uv run ruff format . && uv run ruff check .
uv run mypy .

# Frontend lint/format
bunx biome check --write .

# Local pipeline testing (Inngest dev server)
npx inngest-cli@latest dev                               # separate terminal — serves Inngest UI at localhost:8288
```

## Architecture

### Request → Response
Next.js PWA (Vercel) + Clerk (auth UI) → FastAPI (Cloud Run) via REST + Clerk JWT → Supabase (PostgreSQL)

### Auth flow (Clerk)
- Clerk Next.js SDK handles all auth UI — no auth pages to build
- FastAPI verifies Clerk JWTs via JWKS (`backend/core/auth.py`) on every request
- On first sign-in: Clerk webhook (`POST /api/webhooks/clerk/`) creates User row in Supabase
- No passwords or secrets stored in our DB

### Async AI Pipeline
Video upload → GCS → `inngest_client.send("video/uploaded")` → Inngest durable function:

The pipeline is an Inngest function mounted on FastAPI (`inngest.fast_api.serve()`). Each stage is a `step.run()` call — Inngest handles per-step retries, observability, and deduplication. Local dev: `npx inngest-cli@latest dev` (UI at `localhost:8288`).

0. **Stage 0 — Voice Memo** (`pipeline/stages/voice_memo.py`): Optional. Google STT → `voice_transcript`; Gemini entity extraction → `structured_input`.
1. **Stage 1 — Video Analysis** (`pipeline/stages/video_analysis.py`): Gemini 3 Flash, single-agent structured prompt. Extracts cooking events, environment state, diagnosis, `key_moment_timestamp` in one call.
2. **Stage 2 — RAG** (`pipeline/stages/rag.py`): Embed query with Gemini `gemini-embedding-001` → pgvector similarity search in Supabase → top-3 cooking principles + past session summaries.
3. **Stage 3a — Coaching Text** (`pipeline/stages/coaching_script.py`): Gemini generates `coaching_text` (4-section JSON). Posted to Coaching chat immediately. Session status → `text_ready`. (~2–3 min after upload)
4. **Stage 3b — Narration Script**: Gemini generates `narration_script` (part1 / pivot / part2).
5. **Stage 4 — Video Production** (`pipeline/stages/video_production.py`): Cloud TTS → audio files. FFmpeg: extract 15s clip at `key_moment_seconds`, compose final video → GCS. Video posted to chat. Session status → `completed`. (~5–10 min after upload)

### Backend structure (`backend/`)
- **`core/auth.py`** — Clerk JWKS fetch + JWT verification middleware
- **`core/database.py`** — SQLModel engine pointed at Supabase PostgreSQL
- **`models/`** — SQLModel table models (User, Dish, Session, LearnerState, ChatRoom, Message)
- **`routers/auth.py`** — only `POST /webhooks/clerk/` + `GET /auth/me/`
- **`services/`** — GCS client, Pub/Sub publisher, Stripe client

### Frontend structure (`frontend/`)
Next.js App Router PWA on Vercel. `@clerk/nextjs` for auth. Tanstack Query for all server state. shadcn/ui + Tailwind for components.

### Knowledge base (`knowledge_base/`)
Markdown principles → embedded via Gemini `gemini-embedding-001` (768-dim) → stored in Supabase pgvector table. Run `knowledge_base/ingest.py` to rebuild.

## Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| DB + Vector search | Supabase pgvector | Replaces Cloud SQL + Vertex AI Vector Search; corpus is small (~100–200 principles); one service, cheaper |
| Auth | Clerk | Eliminates auth implementation from scope; JWKS-based JWT verification works cleanly with FastAPI |
| Frontend components | shadcn/ui + Tailwind | Copy-paste ownership model, no version lock-in, Radix UI accessibility |
| Data fetching | Tanstack Query | `refetchInterval` pattern for polling `text_ready → completed` pipeline status |
| Embeddings | Gemini `gemini-embedding-001` | Same API key as LLM; no additional vendor |
| Video analysis | Single-agent structured prompt | Gemini 3 handles full video analysis in one call; dual-agent overhead unnecessary |
| Feedback delivery | Tiered (text first) | Users read diagnosis in ~2–3 min while video encodes; vs Moment's 2-day wait |
| Coaching video storage | GCS path (not URL) | Signed URL generated at read time; no stale URLs in chat history |

## MCP Servers

Two MCP servers are available in this project. Use them instead of raw SQL or Inngest API calls.

### Supabase MCP (`mcp__supabase__*`)
| Tool | Purpose |
|------|---------|
| `execute_sql` | Run SELECT queries, debug data |
| `apply_migration` | DDL changes (CREATE/ALTER/DROP) — preferred over raw `execute_sql` for schema changes |
| `list_tables` | Inspect schema |
| `list_migrations` | See migration history |
| `list_extensions` | Check enabled Postgres extensions |
| `get_logs` | Fetch last-24hr logs by service: `api`, `postgres`, `auth`, `storage`, `realtime`, `edge-function` |
| `get_advisors` | Security/performance advisory notices — run after DDL changes |
| `get_project_url` | Retrieve Supabase project URL |
| `get_publishable_keys` | Retrieve anon/publishable API keys |
| `generate_typescript_types` | Generate TS types from current schema |
| `search_docs` | Search Supabase docs via GraphQL |
| `list_edge_functions` | List deployed Edge Functions |
| `get_edge_function` | Read Edge Function source |
| `deploy_edge_function` | Deploy an Edge Function |
| `create_branch` / `list_branches` / `delete_branch` / `merge_branch` / `reset_branch` / `rebase_branch` | Supabase branching workflow |

### Inngest Dev MCP (`mcp__inngest-dev__*`)
Requires `npx inngest-cli@latest dev` running in a separate terminal (UI at `localhost:8288`).

| Tool | Purpose |
|------|---------|
| `list_functions` | List all registered Inngest functions |
| `send_event` | Fire an event to trigger functions (fire-and-forget) |
| `invoke_function` | Invoke a function and wait for its result |
| `get_run_status` | Get detailed trace/status for a run ID |
| `poll_run_status` | Poll until a run completes |
| `list_docs` | List Inngest documentation categories |
| `read_doc` | Read a specific Inngest doc |
| `grep_docs` | Search Inngest docs by pattern |

## Baked-in constraints
- **Japanese only** (`ja-JP`): all prompts, TTS (Chirp 3 HD `ja-JP-Chirp3-HD-*`), coaching text
- **`gemini-3-flash-preview`** for all AI tasks (API identifier; model is Gemini 3 Flash). `gemini-embedding-001` (768-dim) for embeddings. Both via `GEMINI_API_KEY`.
- **Session limits**: `unique_together=(user_id, dish_id, session_number)` + `CHECK session_number IN (1,2,3)`
- **Pivot line is fixed**: `"動画を使ってそのポイントを見てみましょう"` always the exact string in `narration_script.pivot`
- **Status flow**: `pending_upload → uploaded → processing → text_ready → completed` (or `failed`)
- **Clerk webhook** creates User + ChatRooms on `user.created`; no passwords stored; `clerk_user_id` is the User↔Clerk link
- **No Django anywhere**: FastAPI + SQLModel + Alembic throughout
