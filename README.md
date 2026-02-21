# moment-clone

A clone of [Cookpad's moment](https://cookwithmoment.com) — an AI-powered personal cooking coaching service. Users upload a video of themselves cooking, receive a personalized coaching video with AI voice narration, and repeat the same dish three times to build transferable cooking skills.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python / Django 5.x + Django REST Framework |
| Frontend | Django templates + HTMX |
| Database | PostgreSQL (Cloud SQL) |
| Storage | Google Cloud Storage |
| Async queue | Google Cloud Pub/Sub |
| AI pipeline | Cloud Run Jobs |
| Video analysis | Gemini 3 Flash Preview (multimodal) |
| Coaching LLM | Gemini 3 Flash Preview |
| Vector search | Vertex AI Vector Search |
| TTS | Google Cloud TTS (Neural2 ja-JP) |
| Video composition | FFmpeg |
| Hosting | Google Cloud Run |
| IaC | Terraform |
| CI/CD | Cloud Build |

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (package manager)
- [Docker](https://docs.docker.com/get-docker/)
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) authenticated to a GCP project
- FFmpeg (`brew install ffmpeg` on macOS)
- PostgreSQL 16 (local dev) or Cloud SQL proxy

## Local Development Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd moment-clone

# 2. Install dependencies
uv sync

# 3. Copy environment variables
cp .env.example .env
# Fill in: DATABASE_URL, GCS_BUCKET, GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, etc.

# 4. Run database migrations
uv run python manage.py migrate

# 5. Load seed data (dishes, cooking principles knowledge base)
uv run python manage.py seed_dishes
uv run python manage.py seed_knowledge_base

# 6. Start the development server
uv run python manage.py runserver

# 7. (Separate terminal) Start the Pub/Sub emulator for local pipeline testing
gcloud beta emulators pubsub start --project=local-dev

# 8. (Separate terminal) Run the pipeline worker locally
uv run python pipeline/worker.py --local
```

## Environment Variables

```bash
# Django
SECRET_KEY=
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/moment_clone

# Google Cloud
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Cloud Storage
GCS_BUCKET=moment-clone-media
GCS_COACHING_VIDEO_EXPIRY_DAYS=7

# Pub/Sub
PUBSUB_TOPIC=session-uploaded
PUBSUB_SUBSCRIPTION=pipeline-worker

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3-flash-preview

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
```

## Project Structure

```
moment-clone/
├── manage.py
├── pyproject.toml
├── .env.example
│
├── config/                     # Django project settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── users/                  # User auth, onboarding, learner state
│   ├── dishes/                 # Dish catalogue, progression
│   ├── sessions/               # Cooking sessions, video upload, AI output
│   └── chat/                   # Chat rooms and messages
│
├── pipeline/                   # AI pipeline (Cloud Run Job)
│   ├── worker.py               # Entrypoint — receives Pub/Sub message
│   ├── stages/
│   │   ├── video_analysis.py   # Stage 1: Gemini video analysis (CHEF-VL pattern)
│   │   ├── rag.py              # Stage 2: Vertex AI Vector Search
│   │   ├── coaching_script.py  # Stage 3: Gemini coaching text + narration script
│   │   └── video_production.py # Stage 4: Cloud TTS + FFmpeg composition
│   └── prompts/
│       ├── video_analysis.py
│       ├── coaching_script.py
│       └── system.py
│
├── knowledge_base/             # Cooking principles for RAG
│   ├── principles/             # Markdown files per principle
│   └── ingest.py               # Script to embed and upload to Vector Search
│
├── templates/                  # Django HTML templates
│   ├── base.html
│   ├── dashboard/
│   ├── sessions/
│   └── chat/
│
├── static/                     # CSS, JS, static assets
│   └── audio/
│       └── outro.mp3           # Coaching video outro music
│
├── terraform/                  # GCP infrastructure
│   ├── main.tf
│   ├── variables.tf
│   └── modules/
│       ├── cloud_run/
│       ├── cloud_sql/
│       ├── pubsub/
│       └── storage/
│
└── docs/                       # Project documentation
    ├── architecture.md
    ├── design.md
    ├── product.md
    ├── ai_feasibility.md
    └── principal_engineers_analysis.md
```

## Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=apps --cov=pipeline

# Specific app
uv run pytest apps/sessions/

# Pipeline stages (requires GEMINI_API_KEY)
uv run pytest pipeline/ -m integration
```

## Code Quality

```bash
# Format and lint
uv run ruff format .
uv run ruff check .

# Type checking
uv run mypy .
```

## AI Pipeline

The coaching pipeline runs asynchronously as a Cloud Run Job triggered by Pub/Sub.

```
User uploads video
    → POST /api/sessions/{id}/upload/
    → video stored in GCS
    → Pub/Sub message published
    → Cloud Run Job triggered
    → Stage 1: Video analysis (Gemini, CHEF-VL dual-agent pattern)
    → Stage 2: RAG retrieval (Vertex AI Vector Search)
    → Stage 3: Coaching script generation (Gemini)
    → Stage 4: TTS + FFmpeg video composition
    → coaching_video.mp4 uploaded to GCS
    → Session updated → Messages posted to chat rooms
    → User notified by email
```

See [`docs/design.md`](docs/design.md) for the full pipeline specification.

## Deployment

```bash
# Build and push container
gcloud builds submit --tag gcr.io/$PROJECT_ID/moment-clone

# Apply infrastructure
cd terraform && terraform apply

# Deploy Django app
gcloud run deploy moment-clone \
  --image gcr.io/$PROJECT_ID/moment-clone \
  --region us-central1 \
  --set-env-vars-file .env.production

# Deploy pipeline worker
gcloud run jobs deploy pipeline-worker \
  --image gcr.io/$PROJECT_ID/moment-clone \
  --region us-central1 \
  --command python,pipeline/worker.py
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
