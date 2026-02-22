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

## E2E Testing with Playwright + Clerk

Clerk's development instance uses cross-domain `dvb_` (dev_browser) JWTs. A headless browser visiting the app and accounts.dev separately creates **two unlinked** `dvb_` tokens → `__client_uat=0` on app domain → session never syncs.

### Solution: share Vercel's `dvb_` JWT with accounts.dev

```text
frontend/clerk_login.mjs   # standalone auth helper (saves session to /tmp/clerk_session.json)
frontend/clerk_e2e.mjs     # full E2E screenshot run (all 6 pages)
```

Run from `frontend/` (needs `@playwright/test` installed):

```bash
cd frontend
node clerk_e2e.mjs
# Screenshots → ../e2e-screenshots/
```

### How it works

1. Load `https://moment-clone.vercel.app/` → capture `__clerk_db_jwt` cookie (`dvb_A`)
2. Intercept all `https://<FAPI>/v1/**` requests → append `?__clerk_testing_token=<token>` + force `captcha_bypass: true` (bypasses Turnstile without `+clerk_test` email suffix)
3. Navigate to sign-in token URL **with** `?__clerk_db_jwt=dvb_A` appended — both domains now share the same `dvb_` JWT
4. Session syncs; subsequent navigations to Vercel are authenticated

### Clerk API calls used

| Endpoint | Purpose |
|---|---|
| `POST /v1/testing_tokens` | Get testing token (Turnstile bypass) |
| `POST /v1/sign_in_tokens` | Get one-time sign-in URL for `USER_ID` |

### Bootstrapping a new test user in Supabase

The Clerk webhook creates the User row on `user.created`. If a user exists in Clerk but not in the DB (e.g. account pre-dates backend deployment), create manually:

```sql
INSERT INTO "user" (clerk_user_id, email, first_name, onboarding_done, subscription_status, learner_profile)
VALUES ('<clerk_user_id>', '<email>', '<name>', false, 'inactive', '{}');

-- Get the new user's id, then:
INSERT INTO learnerstate (user_id) VALUES (<id>);
INSERT INTO chatroom (user_id, room_type) VALUES (<id>, 'coaching'), (<id>, 'cooking_videos');
```

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

## Cloud Run IAM Requirements

The `moment-clone-backend` service account needs the following IAM binding (already applied, do not remove):

```bash
# Required for GCS signed URL generation (Cloud Run has no private key, uses IAM signBlob API)
gcloud iam service-accounts add-iam-policy-binding \
  moment-clone-backend@moment-clone.iam.gserviceaccount.com \
  --member="serviceAccount:moment-clone-backend@moment-clone.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=moment-clone
```

Without this, `GET /api/sessions/{id}/` and `GET /api/chat/rooms/*/messages/` return 500 (signed URL endpoints fail with PERMISSION_DENIED).

## Baked-in constraints
- **Japanese only** (`ja-JP`): all prompts, TTS (Chirp 3 HD `ja-JP-Chirp3-HD-*`), coaching text
- **`gemini-3-flash-preview`** for all AI tasks (API identifier; model is Gemini 3 Flash). `gemini-embedding-001` (768-dim) for embeddings. Both via `GEMINI_API_KEY`.
- **Session limits**: `unique_together=(user_id, dish_id, session_number)` for regular dishes (3-session cap enforced in router); free-dish (`slug='free'`) is unlimited — the DB-level `CHECK session_number IN (1,2,3)` was dropped in migration `a008668ec8e0`
- **Pivot line is fixed**: `"動画を使ってそのポイントを見てみましょう"` always the exact string in `narration_script.pivot`
- **Status flow**: `pending_upload → uploaded → processing → text_ready → completed` (or `failed`)
- **Clerk webhook** creates User + ChatRooms on `user.created`; no passwords stored; `clerk_user_id` is the User↔Clerk link
- **No Django anywhere**: FastAPI + SQLModel + Alembic throughout
