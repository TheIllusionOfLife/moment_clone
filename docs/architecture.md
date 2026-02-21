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

## Our Clone (GCP) Full Architecture

```
┌─────────────────────────────────────────────────────┐
│  Marketing LP: Nuxt.js + Firebase + Stripe          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Mobile App: Flutter (iOS + Android)                │
│  Chat rooms: My Coaching / Help / Cooking Videos    │
│  + In-app camera for overhead cooking recording     │
│  + Voice memo recording for self-assessment         │
└──────────────────┬──────────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────────┐
│  Backend: Django + DRF (on Cloud Run)               │
│  - Auth, user management, chat rooms                │
│  - Video upload → Cloud Storage                     │
│  - Triggers Pub/Sub events                          │
│  Cloud SQL (PostgreSQL)                             │
└──────────┬──────────────────────────────────────────┘
           │ Pub/Sub
┌──────────▼──────────────────────────────────────────┐
│  AI Pipeline Workers (Cloud Run Jobs)               │
│  ┌─────────────────────────────────────────────┐   │
│  │ 1. Video Analysis Agent (Gemini 3 Flash Preview)    │   │
│  │    - Analyze full timelapse video           │   │
│  │    - Extract cooking events with timestamps │   │
│  │    - Identify THE key moment timestamp      │   │
│  │      (the clip to show in coaching video)   │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 2. RAG Agent (Vertex AI Vector Search)      │   │
│  │    - Retrieve relevant cooking principles   │   │
│  │    - Retrieve user's past session context   │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 3. Coaching Script Agent (Gemini 3 Flash)   │   │
│  │    - Learner state from Firestore           │   │
│  │    - Generates structured coaching text:    │   │
│  │      🍳 今回の問題点                          │   │
│  │      🍳 身につけるべきスキル                   │   │
│  │      次回試すこと                             │   │
│  │      ✅ 成功のサイン                          │   │
│  │    - Generates 2-part narration script:     │   │
│  │      Part 1: principle + diagnosis          │   │
│  │      [pivot: "動画を使って見てみましょう"]    │   │
│  │      Part 2: narration synced to user clip  │   │
│  ├─────────────────────────────────────────────┤   │
│  │ 4. Video Production (FFmpeg + Cloud TTS)    │   │
│  │    - TTS: Part 1 audio + Part 2 audio       │   │
│  │    - FFmpeg: extract ~15s clip at timestamp │   │
│  │    - FFmpeg compose:                        │   │
│  │        [intro: full timelapse + Part1 TTS]  │   │
│  │        + [user clip + Part2 TTS]            │   │
│  │        + [outro music]                      │   │
│  │    - Upload final .mp4 → Cloud Storage      │   │
│  └─────────────────────────────────────────────┘   │
│  coaching_text → Cloud SQL → chat message          │
│  coaching_video.mp4 → GCS signed URL → chat        │
│  FCM push notification → user                      │
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

| Layer | Moment (AWS) | Our Clone (GCP) |
|---|---|---|
| Marketing LP | Nuxt.js + Firebase + Stripe | Nuxt.js + Firebase + Stripe (same) |
| Mobile App | iOS + Android native | Flutter (iOS + Android) |
| Camera | Dedicated Cook Cam IoT device | Smartphone camera (overhead mount) |
| API backend | Django + DRF on ECS | Django + DRF on Cloud Run |
| Primary DB | PostgreSQL | Cloud SQL (PostgreSQL) |
| Media storage | S3 | Cloud Storage |
| Async event bus | SQS / SNS | Pub/Sub |
| Pipeline workers | Lambda / ECS | Cloud Run Jobs |
| Video analysis | Hybrid: custom CV + foundation model | Gemini 3 Flash Preview (video) + cooking heuristics |
| Key moment detection | Custom CV with timestamp output | Gemini 3 Flash Preview timestamp extraction prompt |
| Knowledge base | Pinecone (4yr proprietary chef data) | Vertex AI Vector Search + manual knowledge base |
| Coaching LLM | Post-trained on chef coaching dataset | Gemini 3 Flash Preview + RAG + structured learner state |
| Learner state | PostgreSQL + custom | Firestore (per-user structured doc) |
| TTS (coaching audio) | Unknown | Google Cloud TTS (Neural2 ja-JP) |
| Video composition | Unknown (FFmpeg likely) | FFmpeg on Cloud Run Jobs |
| Coaching video hosting | moment.page (external) | GCS signed URL or Cloud Run page |
| Chat room names | My Coaching / Help / Cooking Videos | Same |
| IaC | Terraform | Terraform |
| CI/CD | Unknown | Cloud Build |

## AI Agent Comparison

| Agent | Moment | Our Clone |
|---|---|---|
| Video Analysis | Custom-trained CV + foundation model | Gemini 3 Flash Preview: events + timestamps |
| Key Moment Detection | Custom CV classifier | Gemini 3 Flash Preview: "identify the single most important timestamp" |
| RAG | Pinecone + proprietary chef dataset | Vertex AI Vector Search + curated knowledge base |
| Coaching Script | Post-trained LLM, 2-part script structure | Gemini 3 Flash Preview: Part1 (principle/diagnosis) + Part2 (clip narration) |
| Dialogue Manager | Custom intent/entity + fallback/escalation | Gemini 3 Flash Preview with session context |
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
