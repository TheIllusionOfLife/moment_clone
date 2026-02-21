# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend
uv sync
uv run uvicorn backend.main:app --reload

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Seed initial data
uv run python -m backend.scripts.seed_dishes
uv run python -m backend.scripts.seed_knowledge_base

# Frontend
cd frontend && bun install
cd frontend && bun dev

# Run all backend tests
uv run pytest

# Run tests for a specific module
uv run pytest backend/
uv run pytest pipeline/

# Pipeline integration tests (requires GEMINI_API_KEY)
uv run pytest pipeline/ -m integration

# Backend: format and lint
uv run ruff format .
uv run ruff check .
uv run mypy .

# Frontend: format and lint
bunx biome check --write .

# Start Pub/Sub emulator (separate terminal)
gcloud beta emulators pubsub start --project=local-dev

# Run pipeline worker locally (separate terminal)
uv run python pipeline/worker.py --local
```

## Architecture

### Request → Response
Next.js PWA (Vercel) → FastAPI (Cloud Run) via REST + JWT → Cloud SQL (PostgreSQL)

### Async AI Pipeline (the core product)
Video upload → GCS → Pub/Sub message → Cloud Run Job triggers 5-stage pipeline:

0. **Stage 0 — Voice Memo** (`pipeline/stages/voice_memo.py`): Optional pre-stage. Google Cloud STT → `voice_transcript`; Gemini entity extraction → `structured_input`. Skipped if no voice memo.
1. **Stage 1 — Video Analysis** (`pipeline/stages/video_analysis.py`): Single-agent Chain-of-Video-Thought (CoVT) with Gemini 3 Flash (`gemini-3-flash`). One prompt extracts cooking events, environment state, diagnosis, and `key_moment_timestamp`. Idempotency guard: check `session.pipeline_job_id` before processing.
2. **Stage 2 — RAG** (`pipeline/stages/rag.py`): Vertex AI Vector Search over cooking principles knowledge base + past session summaries from `LearnerState`.
3. **Stage 3a — Coaching Text** (`pipeline/stages/coaching_script.py`): Gemini generates `coaching_text` (4-section JSON). Delivered to Coaching chat room immediately (~2–3 min). Session status → `text_ready`.
4. **Stage 3b — Narration Script**: Gemini generates `narration_script` (part1 / pivot / part2).
5. **Stage 4 — Video Production** (`pipeline/stages/video_production.py`): Cloud TTS synthesizes audio for part1 + part2. FFmpeg extracts 15s clip at `key_moment_seconds`, composes `intro_segment + key_moment_segment + outro.mp3` → `coaching_video.mp4` → GCS. Video delivered to chat (~5–10 min). Session status → `completed`.

After pipeline completes, two chat messages are auto-created: raw video in "Cooking Videos" room, coaching text + video in "Coaching" room.

### Backend Structure (`backend/`)
- **`core/`** — `config.py` (pydantic-settings), `database.py` (SQLModel engine + session), `auth.py` (JWT)
- **`models/`** — SQLModel table models: `User`, `Dish`, `UserDishProgress`, `Session`, `LearnerState`, `ChatRoom`, `Message`
- **`routers/`** — FastAPI route handlers: `auth`, `dishes`, `sessions`, `chat`
- **`services/`** — GCS client, Pub/Sub publisher, Stripe client

### Frontend Structure (`frontend/`)
Next.js App Router PWA deployed on Vercel. Routes mirror `/app` directory structure.

### Key design decisions baked in
- **Japanese only** (`ja-JP`): All AI prompts, TTS voice (`ja-JP-Neural2-B`), coaching text in Japanese.
- **Gemini 3 Flash (`gemini-3-flash`)** for all AI (video CoVT + coaching text + narration + Q&A). Use `GEMINI_MODEL=gemini-3-flash`.
- **`Session` model constraints**: `unique_together=(user_id, dish_id, session_number)` + `CheckConstraint session_number IN (1,2,3)`. `raw_video_url` blank until upload. `pipeline_job_id` is idempotency key.
- **GCS path pattern**: Store `coaching_video_gcs_path` (immutable object path). Generate signed URL at read time in API response. Same for `Message.video_gcs_path`.
- **Tiered delivery**: `status` flow is `uploaded → processing → text_ready → completed`. Text message posted after Stage 3a; video message posted after Stage 4.
- **Coaching text format** (4 sections): `🍳 今回の問題点` / `🍳 {N}回目のセッションで身につけるべきスキル` / `次回試すこと` / `✅ 成功のサイン`.
- **Coaching video pivot line is fixed**: `"動画を使ってそのポイントを見てみましょう"` — always the exact string in `narration_script.pivot`.
- **Session limit**: max 3 sessions per dish per user (`session_number` ∈ {1, 2, 3}).
- **No Django anywhere**: FastAPI + SQLModel + Alembic throughout. No Django admin.
- **Auth**: JWT only (no sessions). `python-jose` for token encode/decode.

### Knowledge Base (`knowledge_base/`)
Cooking principles as Markdown in `knowledge_base/principles/`. `knowledge_base/ingest.py` embeds and uploads to Vertex AI Vector Search. The 3 starter dishes (チャーハン, ビーフステーキ, ポモドーロ) encode transferable principles.

### Coaching video structure (confirmed)
```
[Part 1: timelapse + TTS narration]   session intro + core principle + diagnosis
[Pivot]                                "動画を使ってそのポイントを見てみましょう"
[Part 2: user's ~15s clip + TTS]       narration synced to key_moment clip
[Outro]                                outro.mp3 (static/audio/outro.mp3)
```

### Gemini Live Companion Mode (post-PMF)
FastAPI WebSocket at `/ws/companion/{session_id}` → Gemini Live API bidirectional stream → audio back to browser. Frontend at `/companion`. Not in MVP.
