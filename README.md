# moment-clone

A clone of [Cookpad's moment](https://cookwithmoment.com) — an AI-powered personal cooking coaching service. Users upload a video of themselves cooking, receive a personalized coaching video with AI voice narration, and repeat the same dish three times to build transferable cooking skills.

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js (PWA, App Router, Vercel) | PWA replaces native app; no App Store needed |
| Frontend components | shadcn/ui + Tailwind CSS | Owned components (copy-paste, no dependency lock-in); Radix UI accessibility |
| Frontend data fetching | Tanstack Query | Pipeline status polling (`text_ready → completed`) with minimal boilerplate |
| Backend API | Python / FastAPI | Async-native; natural fit for Python AI libraries |
| ORM + Migrations | SQLModel + Alembic | Pydantic-native ORM; pairs naturally with FastAPI |
| Database + Vector search | Supabase (PostgreSQL 16 + pgvector) | Replaces Cloud SQL + Vertex AI Vector Search; cheaper, simpler ops, one connection |
| Embeddings | Gemini Embeddings API (`text-embedding-004`) | Same API key as coaching LLM; no extra vendor |
| Auth | Clerk | Auth UI + session management out of the box; FastAPI verifies JWTs via JWKS |
| File storage | Google Cloud Storage | Large video files; signed URLs for secure delivery |
| Async queue | Google Cloud Pub/Sub | Decouples upload from pipeline execution |
| AI pipeline | Cloud Run Jobs | Isolated Python environment; FFmpeg + GCP libraries |
| Video analysis | Gemini 3 Flash (`gemini-3-flash`) | Single-agent structured prompting; multimodal video input |
| Coaching LLM | Gemini 3 Flash (`gemini-3-flash`) | Consistent model across all AI tasks |
| TTS | Google Cloud TTS (Neural2 ja-JP) | Natural Japanese coaching voice |
| Video composition | FFmpeg | Clip extraction + audio sync + concat |
| Payments | Stripe | Subscriptions |
| IaC | Terraform | GCP infrastructure |
| CI/CD | Cloud Build (backend) + Vercel CI (frontend) | |

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
# Fill in: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY,
#          CLERK_SECRET_KEY, CLERK_WEBHOOK_SECRET, GCS_BUCKET, etc.

# 3. Start Supabase locally
supabase start

# 4. Run database migrations
uv run alembic upgrade head

# 5. Enable pgvector and seed data
uv run python -m backend.scripts.seed_dishes
uv run python -m backend.scripts.seed_knowledge_base  # embeds principles → pgvector

# 6. Start the backend API
uv run uvicorn backend.main:app --reload

# 7. Frontend (separate terminal)
cd frontend
bun install
bun dev

# 8. (Separate terminal) Start the Pub/Sub emulator for local pipeline testing
gcloud beta emulators pubsub start --project=local-dev

# 9. (Separate terminal) Run the pipeline worker locally
uv run python pipeline/worker.py --local
```

## Environment Variables

```bash
# Supabase
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_ROLE_KEY=          # server-side only (never expose to client)

# Clerk
CLERK_SECRET_KEY=
CLERK_WEBHOOK_SECRET=               # for verifying /api/webhooks/clerk/
CLERK_JWKS_URL=                     # https://<your-clerk-domain>/.well-known/jwks.json

# Google Cloud
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Cloud Storage
GCS_BUCKET=moment-clone-media
GCS_SIGNED_URL_EXPIRY_DAYS=7

# Pub/Sub
PUBSUB_TOPIC=session-uploaded
PUBSUB_SUBSCRIPTION=pipeline-worker

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# Google Cloud TTS
TTS_VOICE=ja-JP-Neural2-B
TTS_LANGUAGE=ja-JP

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_MONTHLY=

# Frontend — set in frontend/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
moment-clone/
├── backend/                    # FastAPI application
│   ├── main.py                 # App factory, router registration
│   ├── core/
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # SQLModel engine + Supabase session
│   │   └── auth.py             # Clerk JWT verification via JWKS
│   ├── models/                 # SQLModel table models
│   │   ├── user.py
│   │   ├── dish.py
│   │   ├── session.py
│   │   ├── learner_state.py
│   │   └── chat.py
│   ├── routers/
│   │   ├── auth.py             # POST /webhooks/clerk/ + GET /auth/me/
│   │   ├── dishes.py
│   │   ├── sessions.py
│   │   └── chat.py
│   └── services/               # GCS, Pub/Sub, Stripe clients
│
├── frontend/                   # Next.js PWA (App Router)
│   ├── app/
│   ├── components/             # shadcn/ui components
│   └── lib/                    # Tanstack Query hooks, API client
│
├── pipeline/                   # AI pipeline (Cloud Run Jobs)
│   ├── worker.py               # Entrypoint — receives Pub/Sub message
│   └── stages/
│       ├── voice_memo.py       # Stage 0: STT + entity extraction
│       ├── video_analysis.py   # Stage 1: Gemini structured single-agent
│       ├── rag.py              # Stage 2: Supabase pgvector similarity search
│       ├── coaching_script.py  # Stage 3: coaching text + narration script
│       └── video_production.py # Stage 4: Cloud TTS + FFmpeg
│
├── knowledge_base/             # Cooking principles for RAG
│   ├── principles/             # Markdown files per principle
│   └── ingest.py               # Embed with Gemini → insert into Supabase pgvector
│
├── alembic/                    # Database migrations
│   └── versions/
│
├── terraform/                  # GCP infrastructure
└── docs/                       # Project documentation
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
    → POST /api/sessions/{id}/upload/ → GCS
    → Pub/Sub message published → Cloud Run Job triggered
    → Stage 0: Voice memo STT + entity extraction (optional)
    → Stage 1: Video analysis (Gemini — structured single-agent)
    → Stage 2: RAG retrieval (Supabase pgvector)
    → Stage 3a: Coaching text generated → posted to Coaching chat (~2–3 min)
    → Stage 3b: Narration script generated
    → Stage 4: TTS + FFmpeg video composition → GCS
    → Coaching video posted to Coaching chat (~5–10 min)
```

See [`docs/design.md`](docs/design.md) for the full pipeline specification.

## Deployment

```bash
# Backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/moment-clone-backend ./backend
gcloud run deploy moment-clone-backend \
  --image gcr.io/$PROJECT_ID/moment-clone-backend \
  --region us-central1

# Pipeline worker
gcloud run jobs deploy pipeline-worker \
  --image gcr.io/$PROJECT_ID/moment-clone-backend \
  --command python,pipeline/worker.py

# Frontend
cd frontend && vercel --prod
```

## Documentation

| Document | Purpose |
|---|---|
| [`docs/product.md`](docs/product.md) | Product vision, user flows, business model |
| [`docs/design.md`](docs/design.md) | Data models, API, AI pipeline specification, tech decision rationale |
| [`docs/architecture.md`](docs/architecture.md) | System architecture and stack comparison with Moment |
| [`docs/ai_feasibility.md`](docs/ai_feasibility.md) | Academic paper analysis, AI challenge feasibility |
| [`docs/principal_engineers_analysis.md`](docs/principal_engineers_analysis.md) | Analysis of Moment's AI engineering challenges |

## License

MIT
