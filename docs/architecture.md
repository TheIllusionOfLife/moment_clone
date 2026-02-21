# Moment Clone — Architecture

## Moment (Production) Full Architecture

```
┌─────────────────────────────────────────────────────┐
│  Marketing LP: Nuxt.js + Firebase + Stripe          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Mobile App: iOS + Android                          │
│  (3 chat rooms: Help / Cooking Video / Coaching)    │
└──────────────────┬──────────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────────┐
│  Backend: Django + DRF (on AWS ECS)                 │
│  - Auth, user management, chat rooms                │
│  - Video upload → S3                                │
│  - Triggers SQS events                              │
│  PostgreSQL (main DB)                               │
└──────────┬──────────────────────────────────────────┘
           │ SQS
┌──────────▼──────────────────────────────────────────┐
│  AI Pipeline Workers (Lambda / ECS)                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ 1. Video Analysis Agent                     │   │
│  │    Hybrid CV (custom) + foundation model    │   │
│  │    → cooking events + key moment timestamps │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 2. RAG Agent                                │   │
│  │    Pinecone + cooking principles knowledge  │   │
│  │    (4yr proprietary chef coaching dataset)  │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 3. Coaching Script Agent                    │   │
│  │    LLM + learner state + conversational mem │   │
│  │    → Part 1 script (principle + diagnosis)  │   │
│  │    → Part 2 script (synced to user clip)    │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 4. Video Production                         │   │
│  │    TTS → audio per part                     │   │
│  │    FFmpeg: extract clip at key timestamp    │   │
│  │    FFmpeg: compose final coaching video     │   │
│  └─────────────────────────────────────────────┘   │
│  Result → S3 (coaching_video.mp4) → DB             │
│        → push notification to app                  │
└─────────────────────────────────────────────────────┘
```

## Our Clone (GCP + Vercel) Full Architecture

```
┌─────────────────────────────────────────────────────┐
│  Next.js PWA (Vercel)                    [MVP]      │
│  Chat rooms: My Coaching / Cooking Videos           │
│  Video upload (manual) + voice memo + self-ratings  │
│  /companion: Gemini Live real-time mode  [post-PMF] │
└──────────────────┬──────────────────────────────────┘
                   │ REST + JWT
┌──────────────────▼──────────────────────────────────┐
│  Backend: FastAPI (Cloud Run)                       │
│  - JWT auth, user management, chat rooms            │
│  - Video upload → Cloud Storage                     │
│  - Triggers Pub/Sub events                          │
│  - /ws/companion: WebSocket → Gemini Live [post-PMF]│
│  Supabase (PostgreSQL + pgvector) + SQLModel + Alembic │
└──────────┬──────────────────────────────────────────┘
           │ Pub/Sub
┌──────────▼──────────────────────────────────────────┐
│  AI Pipeline (Cloud Run Jobs)                       │
│  ┌─────────────────────────────────────────────┐   │
│  │ 0. Voice Memo (optional)                    │   │
│  │    - Google STT → voice_transcript          │   │
│  │    - Gemini entity extraction → structured  │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 1. Video Analysis (Gemini)                  │   │
│  │    - Single-agent structured prompting      │   │
│  │    - cooking_events + key_moment + diagnosis│   │
│  ├─────────────────────────────────────────────┤   │
│  │ 2. RAG Agent (Supabase pgvector)            │   │
│  │    - Retrieve relevant cooking principles   │   │
│  │    - Retrieve past session summaries        │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 3a. Coaching Text (Gemini)                  │   │
│  │    - Learner state from PostgreSQL          │   │
│  │    - coaching_text JSON → delivered to chat │   │
│  │      🍳 今回の問題点                          │   │
│  │      🍳 身につけるべきスキル                   │   │
│  │      次回試すこと / ✅ 成功のサイン            │   │
│  │    ★ Text message posted to chat ~2–3 min  │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 3b. Narration Script (Gemini)               │   │
│  │    - Part 1 + pivot + Part 2 JSON           │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 4. Video Production (Cloud TTS + FFmpeg)    │   │
│  │    - TTS: Part 1 + Part 2 audio             │   │
│  │    - FFmpeg: extract ~15s clip at timestamp │   │
│  │    - FFmpeg compose: timelapse+TTS1         │   │
│  │        + user clip+TTS2 + outro             │   │
│  │    - GCS path stored; signed URL at read    │   │
│  │    ★ Video message posted to chat ~5–10 min │   │
│  └─────────────────────────────────────────────┘   │
│  Web Push notification → user (service worker)     │
└─────────────────────────────────────────────────────┘
```

## Coaching Video Format (Confirmed from YouTube Short)

The coaching video is a **produced composite video**, not a generic AI talking head.
Duration: ~90 seconds total.

```
[0:00–0:25]  Intro / timelapse montage
             Background music
             AI narration: session intro + core dish principle
             e.g. "This is Session 1 of your fried rice journey.
                   The essence of great fried rice is not seasoning —
                   it's concentrating the natural flavour of ingredients."

[0:25–0:50]  Diagnosis
             AI names the specific problem found in THIS user's session
             Personalized by user name (e.g. "成光さん")
             Explains the WHY behind the problem

[0:50]       ★ PIVOT LINE
             "動画を使ってそのポイントを見てみましょう"
             ("Let's look at that moment in the video.")
             → CUT TO: user's actual cooking footage clip

[0:50–1:05]  User's cooking clip + synced narration
             AI narrates over the extracted clip in real-time
             Points to observable sensory cues:
             - visual state ("卵の端が固まり始め中心がまだ生の段階で")
             - sound ("シュワシュワという音がしたら")
             Ends with the decisive rule / success signal

[1:05–1:29]  Outro: music + applause
```

## Coaching Chat Message Format (Confirmed from Screenshots)

Delivered as a structured text message in the Coaching chat room,
followed by a video link card:

```
[URL card: coaching video]     ← moment.page/f/[ID] or GCS signed URL

📅 [date]  Session N of [dish]

🍳 今回の問題点
   [Root cause of what went wrong]

🍳 [N]回目のセッションで身につけるべきスキル
   [The one core principle to master]

次回試すこと
   [Single concrete action for next attempt]

✅ 成功のサイン
   [Observable physical cues: sound, texture, visual]

AIコーチからのアドバイス →  [link to video]
```

The Coaching chat room is **two-way** — users can ask follow-up questions
at any time and the AI responds in context of their session.

## Stack Comparison

| Layer | Moment (AWS) | Our Clone (GCP + Vercel) |
|---|---|---|
| Client | iOS + Android native app | Next.js PWA (Vercel) — no App Store needed |
| Frontend components | Unknown | shadcn/ui + Tailwind CSS |
| Frontend data fetching | Unknown | Tanstack Query |
| Camera | Dedicated Cook Cam IoT device | Smartphone camera (overhead mount, native camera app) |
| API backend | Django + DRF on ECS | FastAPI on Cloud Run |
| ORM / Migrations | Django ORM | SQLModel + Alembic |
| Auth | Django sessions | Clerk (Next.js SDK + JWKS verification in FastAPI) |
| Primary DB | PostgreSQL | Supabase (PostgreSQL + pgvector) |
| Vector search | Pinecone (proprietary chef data) | Supabase pgvector — same DB, no separate service |
| Embeddings | Proprietary | Gemini Embeddings API (`text-embedding-004`) |
| Media storage | S3 | Cloud Storage |
| Async event bus | SQS / SNS | Pub/Sub |
| Pipeline workers | Lambda / ECS | Cloud Run Jobs |
| Video analysis | Hybrid: custom CV + foundation model | Gemini 3 Flash (`gemini-3-flash`), single-agent structured prompting |
| Key moment detection | Custom CV with timestamp output | Extracted as part of structured prompt output |
| Knowledge base | Proprietary chef coaching dataset | Curated cooking principles (Markdown → pgvector) |
| Coaching LLM | Post-trained on chef coaching dataset | Gemini 3 Flash (`gemini-3-flash`) + RAG + learner state |
| Learner state | PostgreSQL + custom | Supabase PostgreSQL (LearnerState SQLModel) |
| Feedback latency | Up to 2 days (by design) | ~2–3 min (text) / ~5–10 min (video) |
| Feedback delivery | Single delivery (video only) | Tiered: text first, video follows |
| TTS (coaching audio) | Unknown | Google Cloud TTS (Neural2 ja-JP) |
| Video composition | Unknown (FFmpeg likely) | FFmpeg on Cloud Run Jobs |
| Real-time coaching | None | Gemini Live companion mode (post-PMF) |
| Chat room names | My Coaching / Help / Cooking Videos | My Coaching / Cooking Videos (Help: post-MVP) |
| IaC | Terraform | Terraform |
| CI/CD | Unknown | Cloud Build (backend) + Vercel CI (frontend) |

## AI Agent Comparison

| Agent | Moment | Our Clone |
|---|---|---|
| Video Analysis | Custom-trained CV + foundation model | Gemini 3 Flash (`gemini-3-flash`): single-agent structured prompt (events + timestamps + diagnosis in one call) |
| Key Moment Detection | Custom CV classifier | Gemini 3 Flash (`gemini-3-flash`): extracted as part of structured prompt output |
| RAG | Pinecone + proprietary chef dataset | Supabase pgvector + curated cooking principles |
| Coaching Script | Post-trained LLM, 2-part script structure | Gemini 3 Flash (`gemini-3-flash`): Part1 (principle/diagnosis) + Part2 (clip narration) |
| Dialogue Manager | Custom intent/entity + fallback/escalation | Gemini 3 Flash (`gemini-3-flash`) with session context + conversation history |
| TTS | Unknown | Google Cloud TTS Neural2 |
| Video Composer | Unknown | FFmpeg: clip extraction + audio sync + concat |

## Key Gaps vs. Production Moment

| Gap | Production | MVP Workaround |
|---|---|---|
| Heat level detection | Custom CV model | Gemini video description + heuristic prompts |
| Fine-tuned coaching LLM | Post-trained on 4yr chef dataset | Heavy prompt engineering + RAG knowledge base |
| Auto cooking detection | Custom activity classifier on Cook Cam | Manual start/stop button in app (V2: on-device ML) |
| Feedback latency | ~2 days (by design) | Same async pattern, target: hours |
| Multi-language coaching | 5 countries, localized | Start with Japanese only |
| Hardware camera | Cook Cam (dedicated IoT, self-made) | Phone overhead camera (user-mounted) |
| Coaching video hosting | moment.page (custom domain) | GCS signed URL (V2: custom page) |
