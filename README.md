# moment-clone

A clone of [Cookpad's moment](https://cookwithmoment.com) — an AI-powered personal cooking coaching service. Users upload a video of themselves cooking, receive a personalized coaching video with AI voice narration, and repeat the same dish three times to build transferable cooking skills.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (PWA, deployed on Vercel) |
| Backend API | Python / FastAPI |
| ORM + Migrations | SQLModel + Alembic |
| Database | PostgreSQL (Cloud SQL) |
| Storage | Google Cloud Storage |
| Async queue | Google Cloud Pub/Sub |
| AI pipeline | Cloud Run Jobs |
| Video analysis | Gemini 3 Flash (`gemini-3-flash`, multimodal) |
| Coaching LLM | Gemini 3 Flash (`gemini-3-flash`) |
| Vector search | Vertex AI Vector Search |
| TTS | Google Cloud TTS (Neural2 ja-JP) |
| Video composition | FFmpeg |
| Auth | JWT (python-jose) |
| Payments | Stripe |
| Frontend hosting | Vercel |
| Backend hosting | Google Cloud Run |
| IaC | Terraform |
| CI/CD | Cloud Build (backend) + Vercel CI (frontend) |

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [bun](https://bun.sh) (frontend package manager)
- [Docker](https://docs.docker.com/get-docker/)
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) authenticated to a GCP project
- FFmpeg (`brew install ffmpeg` on macOS)
- PostgreSQL 16 (local dev) or Cloud SQL proxy

## Local Development Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd moment-clone

# 2. Backend: install dependencies and configure
uv sync
cp .env.example .env
# Fill in: DATABASE_URL, GCS_BUCKET, GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, etc.

# 3. Run database migrations
uv run alembic upgrade head

# 4. Seed initial data
uv run python -m backend.scripts.seed_dishes
uv run python -m backend.scripts.seed_knowledge_base

# 5. Start the backend API
uv run uvicorn backend.main:app --reload

# 6. Frontend (separate terminal)
cd frontend
bun install
bun dev

# 7. (Separate terminal) Start the Pub/Sub emulator for local pipeline testing
gcloud beta emulators pubsub start --project=local-dev

# 8. (Separate terminal) Run the pipeline worker locally
uv run python pipeline/worker.py --local
```

## Environment Variables

```bash
# FastAPI
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/moment_clone

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

# Vertex AI
VERTEX_AI_LOCATION=us-central1
VECTOR_SEARCH_INDEX_ENDPOINT=

# Google Cloud TTS
TTS_VOICE=ja-JP-Neural2-B
TTS_LANGUAGE=ja-JP

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_MONTHLY=

# Frontend (set in frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
moment-clone/
├── backend/                    # FastAPI application
│   ├── main.py                 # App factory, router registration
│   ├── core/
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # SQLModel engine + session
│   │   └── auth.py             # JWT logic
│   ├── models/                 # SQLModel table models
│   │   ├── user.py
│   │   ├── dish.py
│   │   ├── session.py
│   │   ├── learner_state.py
│   │   └── chat.py
│   ├── routers/                # FastAPI route handlers
│   │   ├── auth.py
│   │   ├── dishes.py
│   │   ├── sessions.py
│   │   └── chat.py
│   └── services/               # GCS, Pub/Sub, Stripe clients
│
├── frontend/                   # Next.js PWA (App Router)
│   ├── app/
│   ├── components/
│   └── lib/                    # API client, auth helpers
│
├── pipeline/                   # AI pipeline (Cloud Run Jobs)
│   ├── worker.py               # Entrypoint — receives Pub/Sub message
│   └── stages/
│       ├── voice_memo.py       # Stage 0: STT + entity extraction
│       ├── video_analysis.py   # Stage 1: Gemini (single-agent)
│       ├── rag.py              # Stage 2: Vertex AI Vector Search
│       ├── coaching_script.py  # Stage 3: coaching text + narration script
│       └── video_production.py # Stage 4: Cloud TTS + FFmpeg
│
├── knowledge_base/             # Cooking principles for RAG
│   ├── principles/
│   └── ingest.py
│
├── alembic/                    # Database migrations
│   └── versions/
│
├── terraform/                  # GCP infrastructure
└── docs/                       # Project documentation
```

## Running Tests

```bash
# All backend tests
uv run pytest

# Specific module
uv run pytest backend/
uv run pytest pipeline/

# Pipeline integration tests (requires GEMINI_API_KEY)
uv run pytest pipeline/ -m integration
```

## Code Quality

```bash
# Backend (Python)
uv run ruff format .
uv run ruff check .
uv run mypy .

# Frontend (TypeScript)
bunx biome check --write .
```

## AI Pipeline

The coaching pipeline runs asynchronously as a Cloud Run Job triggered by Pub/Sub.
Coaching text is delivered first (~2–3 min), video follows (~5–10 min).

```
User uploads video
    → POST /api/sessions/{id}/upload/
    → video stored in GCS
    → Pub/Sub message published
    → Cloud Run Job triggered
    → Stage 0: Voice memo STT + entity extraction (optional)
    → Stage 1: Video analysis (Gemini (single-agent) — single-agent)
    → Stage 2: RAG retrieval (Vertex AI Vector Search)
    → Stage 3a: Coaching text generation → delivered to chat (~2–3 min)
    → Stage 3b: Narration script generation
    → Stage 4: TTS + FFmpeg video composition
    → coaching_video.mp4 uploaded to GCS
    → Coaching video delivered to chat (~5–10 min)
```

See [`docs/design.md`](docs/design.md) for the full pipeline specification.

## Deployment

```bash
# Backend: build and push container
gcloud builds submit --tag gcr.io/$PROJECT_ID/moment-clone-backend ./backend

# Apply infrastructure
cd terraform && terraform apply

# Deploy FastAPI backend
gcloud run deploy moment-clone-backend \
  --image gcr.io/$PROJECT_ID/moment-clone-backend \
  --region us-central1 \
  --set-env-vars-file .env.production

# Deploy pipeline worker
gcloud run jobs deploy pipeline-worker \
  --image gcr.io/$PROJECT_ID/moment-clone-backend \
  --region us-central1 \
  --command python,pipeline/worker.py

# Frontend: deploy to Vercel
cd frontend && vercel --prod
```

## Documentation

| Document | Purpose |
|---|---|
| [`docs/product.md`](docs/product.md) | Product vision, user flows, business model |
| [`docs/design.md`](docs/design.md) | Data models, API, AI pipeline specification |
| [`docs/architecture.md`](docs/architecture.md) | System architecture and stack comparison with Moment |
| [`docs/ai_feasibility.md`](docs/ai_feasibility.md) | Academic paper analysis, AI challenge feasibility |
| [`docs/principal_engineers_analysis.md`](docs/principal_engineers_analysis.md) | Analysis of Moment's AI engineering challenges |

## License

MIT
