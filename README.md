# moment-clone

A clone of [Cookpad's moment](https://cookwithmoment.com) — an AI-powered personal cooking coaching service. Users upload a video of themselves cooking, receive a personalized coaching video with AI voice narration, and repeat the same dish three times to build transferable cooking skills.

## Architecture

```mermaid
graph TB
    subgraph Client["Client (Vercel)"]
        PWA["Next.js PWA\nClerk auth UI · shadcn/ui + Tailwind"]
    end

    subgraph Backend["Backend (Cloud Run)"]
        API["FastAPI\nClerk JWT verification · SQLModel + Alembic"]
    end

    subgraph Storage["Storage"]
        DB["Supabase\nPostgreSQL + pgvector"]
        GCS["Google Cloud Storage\nvideo files"]
    end

    subgraph Pipeline["AI Pipeline (Inngest durable functions)"]
        S0["Stage 0 · Voice Memo\nGoogle STT + Gemini (optional)"]
        S1["Stage 1 · Video Analysis\nGemini 3 Flash"]
        S2["Stage 2 · RAG\npgvector similarity search"]
        S3a["Stage 3a · Coaching Text\nGemini → chat  ~2–3 min"]
        S3b["Stage 3b · Narration Script\nGemini"]
        S4["Stage 4 · Video Production\nCloud TTS + FFmpeg  ~5–10 min"]
        S0 --> S1 --> S2 --> S3a --> S3b --> S4
    end

    PWA -->|"REST + Clerk JWT"| API
    PWA -->|"PUT video (signed URL)"| GCS
    API <-->|"SQLModel ORM"| DB
    API -->|"issues signed PUT URL"| PWA
    API -->|"confirm-upload → video/uploaded event"| Pipeline
    S3a -->|"text message"| DB
    S4 -->|"video GCS path"| DB
```

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js (PWA, App Router, Vercel) | PWA replaces native app; no App Store needed |
| Frontend components | shadcn/ui + Tailwind CSS | Owned components (copy-paste, no dependency lock-in); Radix UI accessibility |
| Frontend data fetching | Tanstack Query | Pipeline status polling (`text_ready → completed`) with minimal boilerplate |
| Backend API | Python / FastAPI | Async-native; natural fit for Python AI libraries |
| ORM + Migrations | SQLModel + Alembic | Pydantic-native ORM; pairs naturally with FastAPI |
| Database + Vector search | Supabase (PostgreSQL 16 + pgvector) | Replaces Cloud SQL + Vertex AI Vector Search; cheaper, simpler ops, one connection |
| Embeddings | Gemini Embeddings API (`gemini-embedding-001`) | Same API key as coaching LLM; no extra vendor |
| Auth | Clerk | Auth UI + session management out of the box; FastAPI verifies JWTs via JWKS |
| File storage | Google Cloud Storage | Large video files; browser uploads directly via signed URL (bypasses Cloud Run 32 MB limit) |
| AI pipeline | Inngest | Durable step functions in pure Python; mounted on FastAPI; built-in retries + observability |
| Video analysis | Gemini 3 Flash (`gemini-3-flash-preview`) | Single-agent structured prompting; multimodal video input |
| Coaching LLM | Gemini 3 Flash (`gemini-3-flash-preview`) | Consistent model across all AI tasks |
| TTS | Google Cloud TTS (Chirp 3 HD ja-JP) | Natural Japanese coaching voice |
| Video composition | FFmpeg | Clip extraction + audio sync + concat |
| Payments | Stripe | Subscriptions (Phase 4) |
| CI/CD | GitHub Actions (backend) + Vercel native integration (previews) | Keyless GCP auth via WIF; unified secrets in GitHub Environments |

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [bun](https://bun.sh) (frontend package manager)
- [Docker](https://docs.docker.com/get-docker/)
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) authenticated to a GCP project
- [Supabase CLI](https://supabase.com/docs/guides/cli)
- FFmpeg (`brew install ffmpeg` on macOS)

## Local Development Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd moment-clone

# 2. Backend: install dependencies and configure
uv sync
cp .env.example .env
# Fill in: DATABASE_URL, GEMINI_API_KEY, CLERK_SECRET_KEY,
#          CLERK_WEBHOOK_SECRET, GCS_BUCKET, etc.

# 3. Start Supabase locally
supabase start

# 4. Run database migrations
uv run alembic upgrade head

# 5. Seed data
uv run python -m backend.scripts.seed_dishes
uv run python -m backend.scripts.seed_knowledge_base  # embeds principles → pgvector

# 6. Start the backend API
uv run uvicorn backend.main:app --reload

# 7. Frontend (separate terminal)
cd frontend
bun install
bun dev

# 8. (Separate terminal) Start the Inngest dev server for local pipeline testing
npx inngest-cli@latest dev
```

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. Key variables:

```bash
# Database
DATABASE_URL=postgresql://postgres:password@db.<ref>.supabase.co:5432/postgres

# Clerk
CLERK_SECRET_KEY=
CLERK_WEBHOOK_SECRET=               # for verifying /api/webhooks/clerk/
CLERK_JWKS_URL=                     # https://<clerk-domain>/.well-known/jwks.json

# CORS — comma-separated list of allowed origins
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Google Cloud (ADC used in production; gcloud auth application-default login for local dev)
GOOGLE_CLOUD_PROJECT=moment-clone
GCS_BUCKET=moment-clone-media
GCS_SIGNED_URL_EXPIRY_DAYS=7

# Inngest
INNGEST_EVENT_KEY=
INNGEST_SIGNING_KEY=

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Google Cloud TTS
TTS_VOICE=ja-JP-Chirp3-HD-Aoede
TTS_LANGUAGE=ja-JP

# Frontend — set in frontend/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
moment-clone/
├── backend/                    # FastAPI application
│   ├── main.py                 # App factory, router registration, Inngest mount
│   ├── core/
│   │   ├── settings.py         # Pydantic-settings (env vars)
│   │   ├── database.py         # SQLModel engine + get_session dependency
│   │   └── auth.py             # Clerk JWT verification via JWKS
│   ├── models/                 # SQLModel table models
│   │   ├── user.py
│   │   ├── dish.py
│   │   ├── session.py
│   │   ├── learner_state.py
│   │   └── chat.py
│   ├── routers/
│   │   ├── auth.py             # POST /api/webhooks/clerk/ + GET /api/auth/me/
│   │   ├── dishes.py
│   │   ├── sessions.py         # upload-url/ + confirm-upload/ for GCS direct upload
│   │   └── chat.py
│   ├── services/               # GCS client (signed URLs), Inngest client
│   └── tests/                  # pytest suite (auth, sessions, webhook, chat)
│
├── frontend/                   # Next.js PWA (App Router)
│   ├── app/
│   ├── components/             # shadcn/ui components
│   ├── lib/                    # Tanstack Query hooks, API client
│   └── e2e/                    # Playwright E2E tests (@clerk/testing)
│
├── pipeline/                   # AI pipeline (Inngest durable functions)
│   ├── functions.py            # Inngest function + step.run() stages
│   ├── stages/                 # voice_memo, video_analysis, rag, coaching_script, narration_script, video_production
│   └── tests/                  # pytest suite (unit, all external calls mocked)
│
├── knowledge_base/             # Cooking principles for RAG
│   ├── heat_management.md      # Markdown files embedded into pgvector via seed_knowledge_base
│   ├── moisture_control.md
│   └── ingest.py               # Embed with Gemini → insert into Supabase pgvector
│
├── alembic/                    # Database migrations
│   └── versions/
│
├── .github/workflows/
│   ├── ci.yml                  # ruff + mypy + pytest on every push/PR
│   └── deploy.yml              # Docker build → Artifact Registry → Cloud Run (main only)
├── Dockerfile                  # Production image (python:3.12-slim + uv)
└── docs/                       # Project documentation
    ├── screenshots/            # App screenshots
    ├── e2e-screenshots/        # E2E test run screenshots (gitignored)
    └── review_article.txt      # Journalist review of the original Moment service
```

## Running Tests

```bash
uv run pytest
uv run pytest backend/
uv run pytest pipeline/ -m integration   # requires GEMINI_API_KEY
```

## Code Quality

```bash
# Backend
uv run ruff format . && uv run ruff check .
uv run mypy .

# Frontend
bunx biome check --write .
```

## AI Pipeline

Coaching text is delivered first (~2–3 min), video follows (~5–10 min).

```
User uploads video
    → POST /api/sessions/{id}/upload-url/  → signed GCS PUT URL returned
    → PUT video directly to GCS            (bypasses Cloud Run 32 MB limit)
    → POST /api/sessions/{id}/confirm-upload/  → validates GCS path, triggers pipeline
    → inngest_client.send("video/uploaded") → Inngest durable pipeline
    → Stage 0: Self-assessment extraction (optional)
         Path A: audio file → Google STT → Gemini entity extraction
         Path B: typed text (POST /memo-text/) → Gemini entity extraction (STT skipped)
    → Stage 1: Video analysis (Gemini — structured single-agent)
    → Stage 2: RAG retrieval (Supabase pgvector + past session summaries)
    → Stage 3a: Coaching text generated → posted to Coaching chat (~2–3 min)
    → Stage 3b: Narration script generated
    → Stage 4: TTS + FFmpeg video composition → GCS
         Intro: cooking footage looped with narration
         Highlight: 15-second clip at key_moment_seconds with part2 narration
    → Coaching video posted to Coaching chat (~5–10 min)
```

### Dishes

| Slug | Name | Sessions |
|---|---|---|
| `fried-rice` | チャーハン | max 3 |
| `beef-steak` | ビーフステーキ | max 3 |
| `pomodoro` | ポモドーロ | max 3 |
| `free` | 自由投稿 | unlimited (custom dish name per session) |

See [`docs/design.md`](docs/design.md) for the full pipeline specification.

## Deployment

**Backend** — `.github/workflows/deploy.yml` triggers on push to `main`:
1. Authenticates to GCP via Workload Identity Federation (no JSON key files)
2. Builds Docker image from `Dockerfile` (python:3.12-slim + uv)
3. Pushes to Artifact Registry (`asia-northeast1-docker.pkg.dev/moment-clone/...`)
4. Sets GCS bucket CORS policy (allows browser PUT from frontend origins)
5. Deploys to Cloud Run with secrets pulled from Secret Manager (`--timeout=900`)

After deploying schema changes, run migrations manually:
```bash
uv run alembic upgrade head
```

Required GitHub secrets: `WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`, `CLOUD_RUN_SA`

**Frontend** — Vercel deploys automatically on push via GitHub integration. Preview deployments per PR; production on merge to `main`.

## E2E Testing

Uses `@clerk/testing` for Playwright auth. See [`frontend/e2e/`](frontend/e2e/) and [CLAUDE.md](CLAUDE.md#e2e-testing-with-playwright--clerk) for setup.

```bash
cd frontend
APP_URL=https://moment-clone.vercel.app npx playwright test
```

## Documentation

| Document | Purpose |
|---|---|
| [`docs/product.md`](docs/product.md) | Product vision, user flows, business model |
| [`docs/design.md`](docs/design.md) | Data models, API, AI pipeline specification, tech decision rationale |
| [`docs/architecture.md`](docs/architecture.md) | System architecture and stack comparison with Moment |
| [`docs/ai_feasibility.md`](docs/ai_feasibility.md) | Academic paper analysis, AI challenge feasibility |
| [`docs/principal_engineers_analysis.md`](docs/principal_engineers_analysis.md) | Analysis of Moment's AI engineering challenges |
| [`docs/review_article.txt`](docs/review_article.txt) | Journalist review of the original Moment service |

## License

MIT
