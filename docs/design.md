# Moment Clone — Design Document

## MVP Scope

| Decision | Choice | Rationale |
|---|---|---|
| Platform | Web first (Django templates) | Fastest iteration; no app store; mobile later |
| Coaching output | Full coaching video (TTS + FFmpeg) | This IS the product — text-only devalues the core experience |
| Camera input | Manual video upload | Decouples AI pipeline validation from camera complexity |
| Chat rooms | Cooking Videos + Coaching only | Core loop only; Help chat deferred |
| Language | Japanese (ja-JP) | Primary market; single locale simplifies prompts and TTS |

---

## System Components

```
Browser (Django templates + HTMX)
    ↓ multipart upload
Django + DRF (Cloud Run)
    ↓ store raw video
Cloud Storage
    ↓ publish event
Pub/Sub
    ↓ trigger
AI Pipeline (Cloud Run Job)
    ├── Stage 1: Video Analysis Agent    (Gemini 3 Flash Preview)
    ├── Stage 2: RAG Agent               (Vertex AI Vector Search)
    ├── Stage 3: Coaching Script Agent   (Gemini 3 Flash Preview)
    └── Stage 4: Video Production        (Cloud TTS + FFmpeg)
         ↓ upload coaching_video.mp4
Cloud Storage → signed URL
    ↓ write result
Cloud SQL (PostgreSQL)
    ↓ notify user
(email notification in MVP, FCM later)
```

---

## Data Models

### User
```python
class User(AbstractUser):
    first_name       = CharField(max_length=100)
    email            = EmailField(unique=True)
    onboarding_done  = BooleanField(default=False)
    learner_profile  = JSONField(default=dict)
    # {
    #   "cooking_experience_years": 5,
    #   "self_rated_level": "beginner",
    #   "goals": ["cook_without_recipes", "impress_family"],
    #   "dietary": []
    # }
    created_at       = DateTimeField(auto_now_add=True)
```

### Dish
```python
class Dish(Model):
    slug             = SlugField(unique=True)   # "fried-rice", "beef-steak", "pomodoro"
    name_ja          = CharField(max_length=100) # "チャーハン"
    name_en          = CharField(max_length=100)
    description_ja   = TextField()
    principles       = JSONField()
    # [
    #   "moisture_control",
    #   "heat_management",
    #   "oil_coating"
    # ]
    transferable_to  = JSONField()              # ["minestrone", "ratatouille"]
    month_unlocked   = IntegerField(default=1)  # 1 = starter dishes
    order            = IntegerField()
```

### UserDishProgress
```python
class UserDishProgress(Model):
    user             = ForeignKey(User)
    dish             = ForeignKey(Dish)
    status           = CharField(choices=[
                         "not_started", "in_progress", "completed"
                       ])
    started_at       = DateTimeField(null=True)
    completed_at     = DateTimeField(null=True)
```

### Session
```python
class Session(Model):
    """One cook of one dish = one session. Max 3 per dish."""
    user             = ForeignKey(User)
    dish             = ForeignKey(Dish)
    session_number   = IntegerField()           # 1, 2, or 3

    # User input
    raw_video_url    = URLField()               # GCS path (timelapse or full video)
    voice_memo_url   = URLField(null=True)      # GCS path to user's voice self-assessment
    self_ratings     = JSONField(default=dict)
    # {
    #   "appearance": 3,  "taste": 4,
    #   "texture": 2,     "aroma": 3
    # }
    voice_transcript = TextField(blank=True)    # STT output of voice memo
    structured_input = JSONField(default=dict)  # entity-extracted from voice transcript
    # {
    #   "identified_issues": ["oiliness", "moisture"],
    #   "questions": ["rice_addition_timing"],
    #   "emotional_state": "uncertain_but_engaged"
    # }

    # Pipeline state
    status           = CharField(choices=[
                         "uploaded",       # video received
                         "processing",     # pipeline running
                         "completed",      # coaching ready
                         "failed"          # pipeline error
                       ], default="uploaded")
    pipeline_started_at = DateTimeField(null=True)
    pipeline_error   = TextField(blank=True)

    # AI analysis output (Stage 1)
    video_analysis   = JSONField(default=dict)
    # {
    #   "cooking_events": [
    #     { "t": "0:23", "event": "egg_added", "state": "pan_temp: too_high" },
    #     { "t": "0:41", "event": "rice_added", "state": "egg: fully_cooked — ERROR" }
    #   ],
    #   "key_moment_timestamp": "0:41",
    #   "key_moment_seconds": 41,
    #   "diagnosis": "egg fully cooked before rice causes clumping"
    # }

    # Coaching output (Stage 3)
    coaching_text    = JSONField(default=dict)
    # {
    #   "mondaiten":   "Oil was insufficient...",
    #   "skill":       "Moisture evaporation is the basis of all cooking...",
    #   "next_action": "Increase oil to double the current amount",
    #   "success_sign": "パチパチ sound + rice looks shiny and loose"
    # }
    narration_script = JSONField(default=dict)
    # {
    #   "part1": "今回はチャーハン作りの第1回セッションです...",
    #   "pivot": "動画を使ってそのポイントを見てみましょう",
    #   "part2": "熱したフライパンで解いた卵を加えます..."
    # }

    # Video output (Stage 4)
    coaching_video_url = URLField(blank=True)   # GCS signed URL to coaching_video.mp4
    coaching_video_expires_at = DateTimeField(null=True)

    created_at       = DateTimeField(auto_now_add=True)
    updated_at       = DateTimeField(auto_now=True)
```

### LearnerState
```python
class LearnerState(Model):
    """Longitudinal learning model. One per user. Updated after each session."""
    user                  = OneToOneField(User)

    skills_acquired       = JSONField(default=list)
    # ["moisture_control"]

    skills_developing     = JSONField(default=list)
    # ["heat_management", "oil_coating"]

    recurring_mistakes    = JSONField(default=list)
    # [{ "mistake": "over_cook_egg_before_combining", "seen_count": 2 }]

    learning_velocity     = CharField(choices=[
                              "fast", "steady", "slow", "plateau"
                            ], default="steady")

    session_summaries     = JSONField(default=list)
    # [{ "dish": "fried-rice", "session": 1, "key_issue": "...", "key_progress": "..." }]

    next_focus            = CharField(max_length=200, blank=True)
    ready_for_next_dish   = BooleanField(default=False)

    updated_at            = DateTimeField(auto_now=True)
```

### ChatRoom
```python
class ChatRoom(Model):
    ROOM_TYPES = [
        ("cooking_videos", "Cooking Videos"),
        ("coaching",       "My Coaching"),
    ]
    user             = ForeignKey(User)
    room_type        = CharField(choices=ROOM_TYPES)
    created_at       = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "room_type")]
```

### Message
```python
class Message(Model):
    SENDER_CHOICES = [("user", "User"), ("ai", "AI"), ("system", "System")]

    chat_room        = ForeignKey(ChatRoom, related_name="messages")
    sender           = CharField(choices=SENDER_CHOICES)
    session          = ForeignKey(Session, null=True, blank=True)
                       # link to the session this message is about

    # Content (one of these is populated)
    text             = TextField(blank=True)
    video_url        = URLField(blank=True)   # for coaching video delivery
    metadata         = JSONField(default=dict)
    # For system messages:
    # { "type": "coaching_ready", "session_id": 42 }
    # For video messages:
    # { "type": "cooking_video", "session_id": 42, "thumbnail_url": "..." }

    created_at       = DateTimeField(auto_now_add=True)
```

---

## API Endpoints (Django REST Framework)

### Auth
```
POST   /api/auth/register/
POST   /api/auth/login/
POST   /api/auth/logout/
GET    /api/auth/me/
```

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
POST   /api/sessions/                    → create session, get upload URL
POST   /api/sessions/{id}/upload/        → upload raw video → GCS → trigger pipeline
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

### Stage 1 — Video Analysis Agent

**Input**: raw_video_url, dish.slug, session.session_number
**Model**: Gemini 3 Flash Preview (video input)
**Pattern**: CHEF-VL dual-agent

```
Agent A — Action Agent
  Prompt: "Watch this cooking video. List all cooking actions with timestamps.
           Format: [{ t, event, duration }]"

Agent B — Environment State Agent
  Prompt: "Watch this cooking video. At each key moment, describe the state:
           pan temperature (too_low/correct/too_high), ingredient state,
           any visual failure signs (smoke, sticking, clumping)."

Synthesis Agent
  Input: action list + state list + dish recipe graph
  Prompt: "Given these actions and states, identify:
           1. The single most critical mistake or improvement area
           2. The key_moment_timestamp (the frame that best shows the issue)
           3. A one-sentence diagnosis"
```

**Output**: `session.video_analysis` (JSON)

---

### Stage 2 — RAG Agent

**Input**: video_analysis.diagnosis, dish.principles, learner_state
**Store**: Vertex AI Vector Search (cooking principles knowledge base)

```
Query: diagnosis + dish principles
Retrieve: top-3 relevant cooking principles with explanation and examples
Also retrieve: relevant past session summaries from learner_state
```

**Output**: retrieved_context (passed to Stage 3)

---

### Stage 3 — Coaching Script Agent

**Input**: video_analysis, retrieved_context, learner_state, session.structured_input,
          session.session_number, user.first_name
**Model**: Gemini 3 Flash Preview

```
System prompt:
  You are a world-class cooking coach speaking in Japanese.
  Your tone is: encouraging but honest, warm, specific, never vague.
  You explain the WHY behind every observation.
  You never give measurements — only observable states (sound, colour, texture).
  You address the user by first name with さん.
  Sentence endings should feel natural and warm (ましょう、ですね、ください).

Output A — coaching_text (structured JSON):
  {
    "mondaiten":   "今回の最も重要な改善点",
    "skill":       "このセッションで身につける原理原則",
    "next_action": "次回試す具体的な1つのアクション",
    "success_sign": "成功を判断できる感覚的なサイン"
  }

Output B — narration_script (2-part):
  {
    "part1": "intro + principle + diagnosis (30-40 seconds of narration)",
    "pivot": "動画を使ってそのポイントを見てみましょう",
    "part2": "narration synced to the key moment clip (15-20 seconds)"
  }
  part2 must reference: observable cues at key_moment_timestamp
                        (what to look for, what sound to listen for)
                        and end with the decisive rule
```

**Output**: `session.coaching_text`, `session.narration_script`

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
  FFmpeg: trim raw_video to length of part1_audio
  Overlay part1_audio
  → intro_segment.mp4

Step 4 — Compose final video
  FFmpeg concat:
    intro_segment.mp4      (part1 TTS over timelapse)
  + key_moment_clip.mp4    (part2 TTS over user's actual footage)
  + outro.mp4              (music + fade)
  → coaching_video.mp4

Step 5 — Upload
  GCS upload → generate signed URL (7-day expiry)
  Update session.coaching_video_url
  Update session.status = "completed"
```

---

## Chat Message Delivery

After pipeline completes, the system creates two messages automatically:

**In "Cooking Videos" room:**
```python
Message(
    sender="system",
    video_url=raw_video_url,
    metadata={"type": "cooking_video", "session_id": session.id}
)
```

**In "Coaching" room:**
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
Message(
    sender="ai",
    video_url=session.coaching_video_url,
    metadata={"type": "coaching_video", "session_id": session.id}
)
```

---

## Web UI Pages

```
/                        Landing page
/onboarding/             ~40-question learner profile quiz
/dashboard/              Dish selection + progress overview
/dishes/{slug}/          Dish detail + session history
/sessions/new/{slug}/    Upload flow (video upload + voice memo + self-ratings)
/chat/cooking-videos/    Cooking Videos chat room
/chat/coaching/          Coaching chat room (+ follow-up Q&A input)
/sessions/{id}/          Session detail (video analysis + coaching)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 5.x + Django REST Framework |
| Frontend | Django templates + HTMX (no SPA) |
| Database | Cloud SQL (PostgreSQL 16) |
| File storage | Google Cloud Storage |
| Async events | Pub/Sub |
| AI pipeline runner | Cloud Run Jobs |
| Video analysis | Gemini 3 Flash Preview (video input) |
| Coaching LLM | Gemini 3 Flash Preview |
| Vector search | Vertex AI Vector Search |
| TTS | Google Cloud TTS (Neural2 ja-JP) |
| Video composition | FFmpeg (in Cloud Run Job container) |
| Auth | Django sessions (web), JWT later for mobile |
| Payments | Stripe (subscriptions) |
| Hosting | Cloud Run (Django app) |
| IaC | Terraform |
| CI/CD | Cloud Build |
| Package manager | uv |
| Linter/formatter | ruff |

---

## Development Sequence

### Phase 1 — Backend Foundation
1. Django project scaffold (uv, ruff, Cloud SQL)
2. User auth + onboarding quiz
3. Dish + Session models + migrations
4. Video upload endpoint → GCS
5. Pub/Sub publisher on upload

### Phase 2 — AI Pipeline
6. Cloud Run Job scaffold (pipeline entrypoint)
7. Stage 1: Video Analysis Agent (Gemini)
8. Stage 2: RAG Agent (Vertex AI Vector Search + knowledge base)
9. Stage 3: Coaching Script Agent (Gemini)
10. Stage 4: TTS + FFmpeg video composition
11. Pub/Sub → pipeline trigger wiring

### Phase 3 — Chat + Delivery
12. ChatRoom + Message models
13. Auto-message creation after pipeline completes
14. Coaching chat room UI (message list + Q&A input)
15. Cooking Videos chat room UI

### Phase 4 — Web UI
16. Dashboard (dish selection + progress)
17. Session upload flow UI
18. Chat rooms UI (HTMX for real-time feel)
19. Learner state display

### Phase 5 — Polish + Payments
20. Stripe subscription integration
21. Dish unlocking by month
22. Email notifications (pipeline complete)
23. Signed URL refresh logic
