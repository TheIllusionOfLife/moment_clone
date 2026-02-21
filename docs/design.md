# Moment Clone — Design Document

## MVP Scope

| Decision | Choice | Rationale |
|---|---|---|
| Platform | Next.js PWA (Vercel) + FastAPI (Cloud Run) | No native app needed; PWA handles upload, mic, push notifications; no App Store friction |
| Coaching output | Full coaching video (TTS + FFmpeg) | This IS the product — text-only devalues the core experience |
| Camera input | Manual video upload | Decouples AI pipeline validation from camera complexity |
| Chat rooms | Cooking Videos + Coaching only | Core loop only; Help chat deferred |
| Language | Japanese (ja-JP) | Primary market; single locale simplifies prompts and TTS |
| Feedback delivery | Tiered — text first (~2–3 min), video follows (~5–10 min) | Users don't wait for video encoding to read diagnosis |
| Feedback latency target | < 5 minutes to coaching text | vs Moment's 2-day wait — core differentiator |
| Onboarding | 40-question quiz for now | Video-based onboarding under discussion; deferred |
| Gemini Live | Post-PMF feature | Real-time companion mode; requires stable coaching loop first |

---

## System Components

```
Next.js PWA (Vercel) + Clerk (auth UI)
    ↓ REST + Clerk JWT (verified via JWKS)
FastAPI (Cloud Run)
    ↓ store raw video
Cloud Storage
    ↓ publish event
Pub/Sub
    ↓ trigger
AI Pipeline (Cloud Run Job)
    ├── Stage 0: Voice Memo STT + extraction (optional)
    ├── Stage 1: Video Analysis            (Gemini 3 Flash, structured single-agent)
    ├── Stage 2: RAG Agent                 (Supabase pgvector)
    ├── Stage 3a: Coaching Text            → delivered to chat (~2–3 min)
    ├── Stage 3b: Narration Script         (Gemini 3 Flash)
    └── Stage 4: Video Production          (Cloud TTS + FFmpeg)
         ↓ upload coaching_video.mp4
Cloud Storage → GCS path → signed URL at read time
    ↓ write result
Supabase (PostgreSQL + pgvector)
    ↓ coaching video delivered to chat (~5–10 min)
```

---

## Data Models

### User
```python
class User(SQLModel, table=True):
    id:                   Optional[int] = Field(default=None, primary_key=True)
    clerk_user_id:        str = Field(unique=True, index=True)  # from Clerk user.created webhook
    email:                str = Field(unique=True, index=True)
    first_name:           str = Field(max_length=100)
    onboarding_done:      bool = Field(default=False)
    subscription_status:  str = Field(default="free")
    # choices: "free" | "active" | "past_due" | "cancelled"
    # enforced at session creation: free users get 1 trial session only
    learner_profile:      dict = Field(default_factory=dict, sa_column=Column(JSON))
    # {
    #   "cooking_experience_years": 5,
    #   "self_rated_level": "beginner",
    #   "goals": ["cook_without_recipes", "impress_family"],
    #   "dietary": []
    # }
    created_at:           datetime = Field(default_factory=datetime.utcnow)
```

### Dish
```python
class Dish(SQLModel, table=True):
    id:              Optional[int] = Field(default=None, primary_key=True)
    slug:            str = Field(unique=True, index=True)  # "fried-rice", "beef-steak", "pomodoro"
    name_ja:         str = Field(max_length=100)           # "チャーハン"
    name_en:         str = Field(max_length=100)
    description_ja:  str
    principles:      list = Field(default_factory=list, sa_column=Column(JSON))
    # ["moisture_control", "heat_management", "oil_coating"]
    transferable_to: list = Field(default_factory=list, sa_column=Column(JSON))
    # ["minestrone", "ratatouille"]
    month_unlocked:  int = Field(default=1)                # 1 = starter dishes
    order:           int
```

### UserDishProgress
```python
class UserDishProgress(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "dish_id"),)

    id:           Optional[int] = Field(default=None, primary_key=True)
    user_id:      int = Field(foreign_key="user.id", index=True)
    dish_id:      int = Field(foreign_key="dish.id")
    status:       str = Field(default="not_started")
    # choices: "not_started" | "in_progress" | "completed"
    started_at:   Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Session
```python
class Session(SQLModel, table=True):
    """One cook of one dish = one session. Max 3 per dish."""
    __table_args__ = (
        UniqueConstraint("user_id", "dish_id", "session_number"),
        CheckConstraint("session_number IN (1, 2, 3)", name="session_number_1_to_3"),
    )

    id:              Optional[int] = Field(default=None, primary_key=True)
    user_id:         int = Field(foreign_key="user.id", index=True)
    dish_id:         int = Field(foreign_key="dish.id")
    session_number:  int                                # 1, 2, or 3

    # User input
    raw_video_url:       str = Field(default="")        # GCS path — blank until upload completes
    voice_memo_url:      Optional[str] = None           # GCS path to user's voice self-assessment
    self_ratings:        dict = Field(default_factory=dict, sa_column=Column(JSON))
    # { "appearance": 3, "taste": 4, "texture": 2, "aroma": 3 }
    voice_transcript:    str = Field(default="")        # STT output of voice memo
    structured_input:    dict = Field(default_factory=dict, sa_column=Column(JSON))
    # { "identified_issues": [...], "questions": [...], "emotional_state": "..." }

    # Pipeline state
    status:              str = Field(default="pending_upload")
    # "pending_upload" | "uploaded" | "processing" | "text_ready" | "completed" | "failed"
    pipeline_job_id:     Optional[UUID] = Field(default=None)  # idempotency key
    pipeline_started_at: Optional[datetime] = None
    pipeline_error:      str = Field(default="")

    # AI analysis output (Stage 1)
    video_analysis:      dict = Field(default_factory=dict, sa_column=Column(JSON))
    # {
    #   "cooking_events": [{ "t": "0:23", "event": "egg_added", "state": "pan_temp: too_high" }],
    #   "key_moment_timestamp": "0:41",
    #   "key_moment_seconds": 41,
    #   "diagnosis": "egg fully cooked before rice causes clumping"
    # }

    # Coaching output (Stage 3a — text delivered first)
    coaching_text:       dict = Field(default_factory=dict, sa_column=Column(JSON))
    # { "mondaiten": "...", "skill": "...", "next_action": "...", "success_sign": "..." }
    coaching_text_delivered_at: Optional[datetime] = None

    # Narration script (Stage 3b — for video production)
    narration_script:    dict = Field(default_factory=dict, sa_column=Column(JSON))
    # { "part1": "...", "pivot": "動画を使ってそのポイントを見てみましょう", "part2": "..." }

    # Video output (Stage 4)
    # Store immutable GCS object path; signed URL generated at read time in the API response.
    coaching_video_gcs_path: str = Field(default="")   # e.g. "sessions/42/coaching_video.mp4"

    created_at:          datetime = Field(default_factory=datetime.utcnow)
    updated_at:          datetime = Field(default_factory=datetime.utcnow)
```

### LearnerState
```python
class LearnerState(SQLModel, table=True):
    """Longitudinal learning model. One per user. Updated after each session."""
    id:                  Optional[int] = Field(default=None, primary_key=True)
    user_id:             int = Field(foreign_key="user.id", unique=True, index=True)

    skills_acquired:     list = Field(default_factory=list, sa_column=Column(JSON))
    # ["moisture_control"]

    skills_developing:   list = Field(default_factory=list, sa_column=Column(JSON))
    # ["heat_management", "oil_coating"]

    recurring_mistakes:  list = Field(default_factory=list, sa_column=Column(JSON))
    # [{ "mistake": "over_cook_egg_before_combining", "seen_count": 2 }]

    learning_velocity:   str = Field(default="steady")
    # choices: "fast" | "steady" | "slow" | "plateau"

    session_summaries:   list = Field(default_factory=list, sa_column=Column(JSON))
    # [{ "dish": "fried-rice", "session": 1, "key_issue": "...", "key_progress": "..." }]

    next_focus:          str = Field(default="", max_length=200)
    ready_for_next_dish: bool = Field(default=False)

    updated_at:          datetime = Field(default_factory=datetime.utcnow)
```

### ChatRoom
```python
class ChatRoom(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "room_type"),)

    id:         Optional[int] = Field(default=None, primary_key=True)
    user_id:    int = Field(foreign_key="user.id", index=True)
    room_type:  str
    # choices: "cooking_videos" | "coaching"
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Message
```python
class Message(SQLModel, table=True):
    id:           Optional[int] = Field(default=None, primary_key=True)
    chat_room_id: int = Field(foreign_key="chatroom.id", index=True)
    sender:       str
    # choices: "user" | "ai" | "system"
    session_id:   Optional[int] = Field(default=None, foreign_key="session.id")

    # Content — exactly one of text/video_gcs_path is populated per message
    text:             str = Field(default="")
    video_gcs_path:   str = Field(default="")  # signed URL generated at read time
    metadata:         dict = Field(default_factory=dict, sa_column=Column(JSON))
    # { "type": "coaching_ready" | "coaching_video" | "cooking_video", "session_id": 42 }

    created_at:   datetime = Field(default_factory=datetime.utcnow)
```

---

## API Endpoints

### Auth
Auth UI (sign-in, sign-up, user management) is handled entirely by Clerk's Next.js SDK.
FastAPI never issues or stores passwords — it only verifies Clerk JWTs via JWKS.

```
POST   /api/webhooks/clerk/     → Clerk calls this on user.created / user.updated
                                  On user.created: creates User row + ChatRoom rows (coaching + cooking_videos)
                                  Webhook signature verified via svix-signature header (CLERK_WEBHOOK_SECRET)
POST   /api/webhooks/stripe/    → Stripe subscription lifecycle events
                                  (customer.subscription.created/updated/deleted → User.subscription_status)
GET    /api/auth/me/            → returns current user from Supabase (JWT required)
```

All other endpoints require `Authorization: Bearer <clerk_session_token>`.
FastAPI middleware fetches Clerk JWKS and verifies the token on each request.
All session and chat endpoints filter by `user_id = current_user.id` to prevent IDOR.

### Onboarding
```
POST   /api/onboarding/          → save learner_profile, mark onboarding_done
```

### Dishes
```
GET    /api/dishes/              → list unlocked dishes for current user
GET    /api/dishes/{slug}/       → dish detail + user progress
```

### Sessions
```
GET    /api/sessions/?dish_slug={slug}   → list sessions for a dish (current user only)
POST   /api/sessions/                    → create session, get upload URL
POST   /api/sessions/{id}/upload/        → upload raw video → GCS → set status="uploaded" → trigger pipeline
POST   /api/sessions/{id}/voice-memo/    → upload voice memo → GCS
PATCH  /api/sessions/{id}/ratings/       → save self-assessment ratings
GET    /api/sessions/{id}/               → session detail + coaching output
```

### Chat
```
GET    /api/chat/rooms/                  → list user's chat rooms
GET    /api/chat/rooms/{type}/messages/  → paginated message history
POST   /api/chat/rooms/{type}/messages/  → send user message (coaching Q&A)
```

### Learner State
```
GET    /api/learner-state/               → current learner state
```

---

## AI Pipeline Specification

Triggered by Pub/Sub message after video upload. Runs as Cloud Run Job.

### Stage 0 — Voice Memo Processing (pre-pipeline, optional)

If `voice_memo_url` is set, run before the main pipeline stages:

```
Step 1 — STT
  Google Cloud Speech-to-Text → voice_transcript (ja-JP)
  Fallback: if no voice memo, voice_transcript = ""

Step 2 — Entity extraction
  Gemini prompt: "Extract from this cooking self-assessment transcript:
    identified_issues (list), questions (list), emotional_state (string)"
  → structured_input JSON
  Fallback: if transcript empty, structured_input = {}
```

**Output**: `session.voice_transcript`, `session.structured_input`

---

### Stage 1 — Video Analysis Agent

**Input**: raw_video_url, dish.slug, session.session_number
**Model**: Gemini 3 Flash (`gemini-3-flash`) (video input)
**Pattern**: Single-agent structured video analysis

Gemini 3's context window handles full cooking video analysis in one call.
The dual-agent pattern (CHEF-VL) is unnecessary overhead.

```
Prompt: "Watch this cooking video of {dish_name}. Think step by step:

  1. List all cooking events with timestamps: [{ t, event, duration }]
  2. At each event, describe the environment state:
     pan temperature (too_low/correct/too_high), ingredient state,
     any visual failure signs (smoke, sticking, clumping)
  3. Identify THE single most critical mistake or improvement area
  4. Identify the key_moment_timestamp (best frame showing the issue)
  5. Write a one-sentence diagnosis

  Output as JSON: { cooking_events, key_moment_timestamp,
                    key_moment_seconds, diagnosis }"
```

**Idempotency guard** (pipeline entrypoint):
```python
if session.pipeline_job_id and session.status not in ("failed", "uploaded"):
    return  # already processing or completed — at-least-once Pub/Sub delivery guard
            # "failed" sessions are retryable; "uploaded" is the expected entry state
session.pipeline_job_id = uuid4()
session.status = "processing"
session.save()
```

**Pub/Sub retry policy**: Pub/Sub redelivers on non-ack up to 7 days. Dead-letter topic (`pipeline-worker-dlq`) configured for messages that exceed 5 delivery attempts. Failed sessions (`status="failed"`) can be manually re-triggered or retried via a future admin endpoint.

**Output**: `session.video_analysis` (JSON)

---

### Knowledge Base Schema (`cooking_principles` table)

```sql
-- Alembic migration: enable pgvector then create table
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE cooking_principles (
    id            SERIAL PRIMARY KEY,
    principle_text TEXT NOT NULL,
    category      VARCHAR(100),          -- e.g. "heat_management", "moisture_control"
    embedding     vector(768) NOT NULL,  -- gemini-embedding-001 output dimension
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- HNSW index for approximate nearest-neighbour search (faster than IVFFlat at this scale)
CREATE INDEX ON cooking_principles USING hnsw (embedding vector_cosine_ops);
```

Populated by `knowledge_base/ingest.py`: reads Markdown files → embeds with `gemini-embedding-001` → inserts rows.

---

### Stage 2 — RAG Agent

**Input**: video_analysis.diagnosis, dish.principles, learner_state
**Store**: Supabase pgvector (cooking principles knowledge base)
— pgvector chosen over Vertex AI Vector Search: smaller corpus (~100–200 principles),
  no GCP-specific indexing overhead, same PostgreSQL connection already in use

```
Step 1 — Embed query
  Gemini Embeddings API (gemini-embedding-001):
  query_text = diagnosis + " " + dish.principles.join(", ")
  query_vector = embed(query_text)  # → 768-dimensional vector

Step 2 — pgvector similarity search
  SELECT * FROM cooking_principles
  ORDER BY embedding <=> query_vector
  LIMIT 3;

Step 3 — Retrieve session context
  Pull relevant past session summaries from learner_state (already in PostgreSQL)
```

**Output**: retrieved_context (passed to Stage 3a)

---

### Stage 3a — Coaching Text Agent (delivered immediately)

**Input**: video_analysis, retrieved_context, learner_state, session.structured_input,
          session.session_number, user.first_name
**Model**: Gemini 3 Flash (`gemini-3-flash`)
**Delivery**: Immediately after this stage — creates coaching text Message in chat (~2–3 min)

```
System prompt:
  You are a world-class cooking coach speaking in Japanese.
  Your tone is: encouraging but honest, warm, specific, never vague.
  You explain the WHY behind every observation.
  You never give measurements — only observable states (sound, colour, texture).
  You address the user by first name with さん.
  Sentence endings should feel natural and warm (ましょう、ですね、ください).

Output — coaching_text (structured JSON):
  {
    "mondaiten":    "今回の最も重要な改善点",
    "skill":        "このセッションで身につける原理原則",
    "next_action":  "次回試す具体的な1つのアクション",
    "success_sign": "成功を判断できる感覚的なサイン"
  }
```

After Stage 3a completes:
  - Persist `session.coaching_text`
  - Set `session.status = "text_ready"`
  - Create Message in Coaching room (formatted text, sender="ai")
  - Update LearnerState:
      - Append to `session_summaries`: { dish, session_number, key_issue (diagnosis), key_progress }
      - Increment `recurring_mistakes` count if same mistake seen before
      - Move skills from `skills_developing` → `skills_acquired` if session 3 completed cleanly
  - User can read coaching while video is still being produced

**Output**: `session.coaching_text`, `session.status = "text_ready"`

---

### Stage 3b — Narration Script Agent

**Input**: coaching_text, video_analysis, user.first_name
**Model**: Gemini 3 Flash (`gemini-3-flash`)

```
Output — narration_script (2-part, feeds Stage 4):
  {
    "part1": "intro + principle + diagnosis (30-40 seconds of narration)",
    "pivot": "動画を使ってそのポイントを見てみましょう",
    "part2": "narration synced to the key moment clip (15-20 seconds)"
  }
  part2 must reference: observable cues at key_moment_timestamp
                        (what to look for, what sound to listen for)
                        and end with the decisive rule
```

**Output**: `session.narration_script`

---

### Stage 4 — Video Production

**Input**: raw_video_url, narration_script, key_moment_seconds, key_moment_duration=15
**Tools**: Google Cloud TTS + FFmpeg

```
Step 1 — TTS
  part1_audio = CloudTTS(narration_script.part1, voice="ja-JP-Neural2-B")
  part2_audio = CloudTTS(narration_script.part2, voice="ja-JP-Neural2-B")
  outro_music = static asset (applause + fade)

Step 2 — Clip extraction
  FFmpeg: extract 15s clip from raw_video at key_moment_seconds
  → key_moment_clip.mp4

Step 3 — Intro segment
  Note: MVP expects users to upload a timelapse of their cooking session
  (phone timelapse mode, or any sped-up cooking video). The intro plays
  this timelapse as background while TTS1 narrates.
  FFmpeg: loop/trim timelapse to match part1_audio duration
  Mix: -filter_complex "[0:v][1:a]" (timelapse stream + part1 audio, mute original)
  → intro_segment.mp4

Step 4 — Key moment segment
  FFmpeg: overlay part2_audio onto key_moment_clip starting at t=0
  Audio starts simultaneously with video; clip duration = max(clip_duration, part2_audio_duration)
  Mix: -filter_complex "[0:v][1:a]amerge" (replace clip audio with narration)
  → key_moment_segment.mp4

Step 5 — Compose final video
  FFmpeg concat (concat demuxer, same codec):
    intro_segment.mp4      (part1 TTS over timelapse)
  + key_moment_segment.mp4 (part2 TTS synced to user's actual footage)
  + outro.mp4              (outro.mp3 over black frame or freeze)
  → coaching_video.mp4

Step 6 — Upload
  GCS upload → store object path in session.coaching_video_gcs_path
  (e.g. "sessions/{session_id}/coaching_video.mp4")
  Signed URL generated at read time in the API serializer (7-day expiry)
  Update session.status = "completed"
```

---

## Chat Message Delivery

After pipeline completes, the system creates two messages automatically:

**In "Cooking Videos" room:**
```python
Message(
    sender="system",
    video_gcs_path=session.raw_video_url,  # signed URL generated at read time
    metadata={"type": "cooking_video", "session_id": session.id}
)
```

**In "Coaching" room (Stage 3a — delivered at text_ready):**
```python
Message(
    sender="ai",
    text=format_coaching_text(session.coaching_text, session),
    # Rendered as:
    # 🍳 今回の問題点
    # {mondaiten}
    # 🍳 {N}回目のセッションで身につけるべきスキル
    # {skill}
    # 次回試すこと
    # {next_action}
    # ✅ 成功のサイン
    # {success_sign}
    metadata={"type": "coaching_ready", "session_id": session.id}
)
```

**In "Coaching" room (Stage 4 — delivered at completed):**
```python
Message(
    sender="ai",
    video_gcs_path=session.coaching_video_gcs_path,  # signed URL generated at read time
    metadata={"type": "coaching_video", "session_id": session.id}
)
```

---

## Coaching Chat Q&A Flow

Users can send follow-up questions in the Coaching room after receiving feedback.

```
POST /api/chat/rooms/coaching/messages/
  { "text": "なぜ卵を先に入れてはいけないのですか？" }

→ Message(sender="user", ...) persisted

→ Background task (Pub/Sub or FastAPI BackgroundTasks):
    1. Load context:
       - Last N messages in coaching room (conversation history)
       - session = most recent completed session for this user
       - session.coaching_text, session.video_analysis, session.dish.principles
       - learner_state

    2. Gemini call (gemini-3-flash):
       System: [coaching persona + Japanese language prompt]
       Context: coaching feedback already given + conversation history
       User message: their question

    3. Persist AI response:
       Message(sender="ai", text=response, session=session, ...)

    4. (MVP: polling or HTMX refresh; V2: WebSocket push)
```

**Fallback**: if no completed session exists, AI responds with a general cooking tip
and prompts the user to complete their first session.

---

## Web UI Pages (Next.js App Router)

```
app/
├── page.tsx                          /          Landing page
├── onboarding/page.tsx               /onboarding   ~40-question learner profile quiz
├── dashboard/page.tsx                /dashboard    Dish selection + progress overview
├── dishes/[slug]/page.tsx            /dishes/:slug Dish detail + session history
├── sessions/new/[slug]/page.tsx      /sessions/new/:slug  Upload flow
│                                                   (video upload + voice memo + ratings)
├── sessions/[id]/page.tsx            /sessions/:id Session detail + coaching output
└── chat/
    ├── cooking-videos/page.tsx       /chat/cooking-videos  Cooking Videos room
    └── coaching/page.tsx             /chat/coaching        Coaching room + Q&A input
```

PWA manifest configured for "Add to Home Screen" install on iOS/Android.
Push notifications via Web Push API (service worker).

---

## Gemini Live Companion Mode (Post-PMF Feature)

Real-time cooking guidance via Gemini Live API. **Not in MVP — build after core loop is validated.**

### What it does

Phone mounted overhead during cooking. User opens `/companion` in browser.
Gemini watches the live video stream and speaks real-time coaching via audio output.

```
User: opens /companion in browser, presses Start
  → getUserMedia() opens camera + microphone
  → WebRTC stream → FastAPI WebSocket endpoint
  → FastAPI streams frames to Gemini Live API
  → Gemini detects key moments: "Your oil is ready — add the egg now"
  → Audio response streamed back → played in browser
```

### Architecture

```
Next.js /companion page
    ↓ WebSocket
FastAPI /ws/companion/{session_id}
    ↓ Gemini Live API (bidirectional stream)
    ↓ audio output
Browser (speaker)
```

### Design constraints
- Separate from the coaching loop — companion is for practice, coaching is for reflection
- No data written to Session model during companion mode (different product mode)
- Requires stable connection; degraded gracefully if connection drops
- Kitchen noise / steam handled by Gemini Live's multimodal robustness
- Privacy note: live video is streamed but not stored
- **Production path**: raw WebSocket is sufficient for prototype; for production stability use WebRTC + LiveKit (Google's recommended wrapper for Gemini Live as of 2026)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (PWA, App Router, deployed on Vercel) |
| Frontend components | shadcn/ui + Tailwind CSS |
| Frontend data fetching | Tanstack Query |
| Backend API | Python / FastAPI |
| ORM + Migrations | SQLModel + Alembic |
| Database + Vector search | Supabase (PostgreSQL 16 + pgvector) |
| Embeddings | Gemini Embeddings API (`gemini-embedding-001`, 768-dim) |
| File storage | Google Cloud Storage |
| Async events | Pub/Sub |
| AI pipeline runner | Cloud Run Jobs |
| Video analysis | Gemini 3 Flash (`gemini-3-flash`, single-agent structured prompting) |
| Coaching LLM | Gemini 3 Flash (`gemini-3-flash`) |
| TTS | Google Cloud TTS (Chirp 3 HD ja-JP) |
| Video composition | FFmpeg (in Cloud Run Job container) |
| Auth | Clerk (Next.js SDK + FastAPI JWT verification via JWKS) |
| Payments | Stripe (subscriptions) |
| Frontend hosting | Vercel |
| Backend hosting | Cloud Run (FastAPI) |
| IaC | Terraform |
| CI/CD | Cloud Build (backend) + Vercel CI (frontend) |
| Python package manager | uv |
| Python linter/formatter | ruff |
| Frontend package manager | bun |
| Frontend linter/formatter | Biome |

## Tech Decision Rationale

**Supabase (PostgreSQL + pgvector)** replaces both Cloud SQL and Vertex AI Vector Search.
- pgvector handles the cooking principles knowledge base; the corpus is small (~100–200 principles) and pgvector is sufficient at this scale
- Eliminates a GCP-specific service (Vertex AI Vector Search) that requires VPC peering, dedicated index endpoints, and per-query billing
- Single database for both relational data and vector search — simpler ops, one connection string
- Cheaper: Supabase Pro ($25/month) vs Cloud SQL + Vertex AI Vector Search indexing fees

**Clerk** replaces hand-rolled JWT auth.
- Next.js SDK provides auth UI (sign-in, sign-up, user management) out of the box — no auth pages to build
- FastAPI verifies Clerk-issued JWTs via Clerk's JWKS endpoint — no shared secret needed
- User record in Supabase created via Clerk webhook on first sign-in (sync pattern)
- Eliminates the full auth implementation from Phase 1 scope

**shadcn/ui + Tailwind CSS** for frontend components.
- Ownership model: components are copied into the repo, not installed as a dependency — no version lock-in
- Radix UI primitives underneath ensure accessibility out of the box
- Tailwind is the standard pairing for Next.js App Router projects

**Tanstack Query** for frontend server state.
- Handles caching, background refetch, stale-while-revalidate — essential for polling pipeline status
- `useQuery` with `refetchInterval` is the natural pattern for watching `text_ready → completed` transitions
- Eliminates hand-rolled `useEffect` + `fetch` patterns

---

## Development Sequence

### Phase 1 — Backend Foundation
1. FastAPI project scaffold (uv, ruff, SQLModel, Alembic)
2. Clerk webhook handler (`POST /webhooks/clerk/`): create User + ChatRooms on `user.created`; `GET /auth/me/`
3. Dish + Session + LearnerState models + Alembic migrations
4. Video upload endpoint → GCS
5. Pub/Sub publisher on upload

### Phase 2 — AI Pipeline
6. Cloud Run Job scaffold (pipeline entrypoint + idempotency guard)
7. Stage 0: Voice memo STT + entity extraction (optional pre-stage)
8. Stage 1: Video Analysis Agent (Gemini, structured single-agent)
9. Stage 2: RAG Agent (Supabase pgvector similarity search)
10. Stage 3a: Coaching text → deliver to chat immediately (`text_ready`)
11. Stage 3b: Narration script generation
12. Stage 4: TTS + FFmpeg video composition → GCS path
13. Pub/Sub → pipeline trigger wiring

### Phase 3 — Frontend (Next.js)
14. Next.js scaffold (App Router, Biome, bun, Vercel deploy)
15. Auth flow (login, register, JWT storage)
16. Onboarding quiz page
17. Dashboard + dish selection
18. Session upload flow (video + voice memo + ratings)
19. Chat rooms (Cooking Videos + Coaching, polling or SSE for new messages)
20. PWA manifest + Web Push service worker

### Phase 4 — Polish + Payments
21. Stripe subscription integration + entitlement guard
22. Dish unlocking by month
23. Pipeline progress indicator (SSE from FastAPI)

### Phase 5 — Gemini Live
24. `/companion` WebSocket endpoint (FastAPI)
25. Gemini Live API integration (bidirectional stream)
26. Companion mode UI (Next.js, getUserMedia)
