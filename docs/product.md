# Product Overview — moment-clone

This document defines the product's purpose, target users, key features, and business
objectives. It is intended to help engineers and AI agents understand the *why* behind
technical decisions and ensure solutions stay aligned with product goals.

---

## What Is This Product?

A personal AI cooking coach. Not a recipe app.

The user cooks a dish, uploads a video of themselves cooking, and receives a personalized
coaching video: AI voice narration over their own cooking footage, identifying the exact
moment where their technique can improve and explaining the underlying principle.

They repeat the same dish three times. Each time, the coaching advances. By the third
session, they have internalised a principle that transfers to dozens of other dishes.

**The core insight**: cooking skill comes from understanding *why*, not from following
steps. A recipe tells you what to do. A coach tells you why it works — and that knowledge
is generative.

---

## The Problem We Solve

Most people cook by following recipes. This creates dependency, not skill:

- They cannot adapt when an ingredient is missing
- They cannot diagnose why a dish failed
- They repeat the same mistakes indefinitely
- They feel no ownership over their cooking

Recipe sites (including Cookpad itself) have made this problem worse, not better.
The goal is to undo it.

---

## Target Users

**Primary**: Busy professionals in their 30s–50s, Japanese market (initial).
- Cook regularly but feel stuck at the same skill level
- Want to improve but cannot attend cooking classes
- Willing to pay a monthly subscription for structured skill development
- Value understanding *why* things work, not just *what* to do

**Secondary** (future): Same profile in UK, France, Italy, Indonesia.

**Not the target user**:
- Professional chefs or culinary students
- Casual cooks who just want quick dinner ideas
- Users who want recipes — they should use Cookpad proper

---

## Key Features

### 1. Cooking Video Upload
User records themselves cooking (any camera), uploads the video. No special hardware
required in MVP. The video is stored and processed asynchronously.

### 2. AI Video Analysis
Gemini analyses the timelapse video using a single-agent structured analysis pattern:
- Single pass extraction: what did the user do and when, plus inferred environment state
- Identifies the single most impactful mistake or improvement area
- Extracts the key moment timestamp for use in the coaching video

### 3. Coaching Video Generation
A personalized ~90-second coaching video is produced:
- Part 1: AI voice narration over intro/timelapse — states the core cooking principle
  and names the specific issue found in this session, addressing user by first name
- Pivot: "動画を使ってそのポイントを見てみましょう" — cuts to user's actual footage
- Part 2: AI narration synced to the extracted clip — references observable cues
  (sound, texture, visual state) and ends with the decisive rule
- Outro: music fade

### 4. Structured Coaching Text
Delivered in the Coaching chat room alongside the video:
```
🍳 今回の問題点       ← root cause of what went wrong
🍳 身につけるべきスキル ← the one transferable principle
次回試すこと          ← single concrete action for next attempt
✅ 成功のサイン        ← observable physical cue (sound, texture, visual)
```

### 5. Three-Session Progression
Each dish is practiced exactly 3 times. The coaching advances each session:
- Session 1: diagnose the fundamental issue
- Session 2: address the root cause, introduce the principle
- Session 3: refine and consolidate — the user should now feel the principle

After 3 sessions, the user has internalised a skill that transfers to other dishes.

### 6. Dish Catalogue with Deliberate Selection
Starter dishes are not chosen for popularity — they are chosen because each teaches
maximally transferable principles:

| Dish | Core Principle | Transfers To |
|---|---|---|
| チャーハン (Fried Rice) | Moisture control, heat management | Minestrone, Ratatouille, any sauté |
| ビーフステーキ (Beef Steak) | Maillard reaction, resting | Any pan-seared protein |
| ポモドーロ (Pomodoro) | Acid reduction, building depth | Any tomato-based sauce |

Month 2+ unlocks 3 more dishes (e.g. 野菜炒め — highest "transformation rate").

### 7. Learner State
The system maintains a longitudinal learner model per user:
- Skills acquired, skills developing, recurring mistakes
- Learning velocity (fast / steady / slow / plateau)
- Readiness for the next dish
- This personalises every coaching session and surfaces patterns across dishes

### 8. Coaching Chat Q&A
After receiving coaching, users can ask follow-up questions in the Coaching chat room.
The AI responds in full context of their specific session and learner history.

---

## What This Product Is NOT

These are explicit non-goals. Do not build them unless specified:

- **Not a recipe app** — no recipe browsing, no ingredient lists, no step-by-step instructions
- **Not a meal planner** — no weekly menus, no shopping lists
- **Not real-time coaching** — coaching is always async (pipeline runs after cook)
- **Not a social platform** — no sharing, no likes, no public profiles
- **Not a food photo app** — the camera records *process*, not plating
- **Not a calorie/nutrition tracker** — irrelevant to the skill-building mission

---

## Coaching Philosophy (Engineering Implications)

Every technical decision should be evaluated against these principles:

### 1. Principles over steps
The AI must explain *why*, not just *what*. A coaching output that says
"add more oil next time" is insufficient. It must explain that oil transfers
heat uniformly to ingredients, and that insufficient oil means uneven cooking
that cannot be corrected by seasoning.

> **Engineering implication**: The coaching prompt must explicitly require
> the *why* behind every observation. RAG retrieval must surface the
> underlying principle, not just the corrective action.

### 2. Observable cues, not measurements
Never say "cook for 3 minutes" or "add 2 tablespoons of oil". Always say
"when you hear パチパチ" or "when the edges set but the centre is still raw".
Observable, physical, transferable.

> **Engineering implication**: The coaching system prompt must prohibit
> time and quantity specifications and require sensory cue descriptions.

### 3. Repetition is the product
The 3-session structure is not a constraint — it is the pedagogical mechanism.
The coaching should explicitly reference previous sessions and frame each new
session in terms of progress made.

> **Engineering implication**: The learner state and session history must
> always be injected into the coaching context. Session 2 coaching must
> reference session 1. Session 3 must show the arc.

### 4. Failure is progress
Session 2 often gets worse before it gets better (following advice precisely
often overcorrects). The AI must frame this as expected and positive —
"you showed great discipline in applying the feedback, and that's real progress
even when the result isn't perfect yet."

> **Engineering implication**: The coaching prompt should include
> framing guidance for session 2 specifically. Never sound disappointed.

### 5. Obsessive language quality
The specific words matter. Japanese sentence endings (ましょう vs ですね vs ください),
the balance of praise and correction, the moment of encouragement vs challenge —
these are engineered, not written casually.

> **Engineering implication**: The coaching system prompt must specify
> tone, sentence ending style, praise-to-correction ratio, and the
> structure of the 90-second narration in detail. Test with real Japanese
> speakers before shipping.

---

## Business Model

| Item | Detail |
|---|---|
| Monthly subscription | ¥9,800/month |
| Trial | Free first session (no card required) |
| Dish unlocking | 3 new dishes per month active |
| Target LTV | 6+ months (skill development takes time) |
| Target CAC | Organic + content marketing (build-in-public, technical blog) |

**Revenue driver**: retention. Users who experience the session-3 breakthrough
(the dish clicks) stay. Users who don't reach session 3 churn. Coaching quality
directly drives LTV.

---

## Success Metrics

| Metric | Target | Why |
|---|---|---|
| Session 3 completion rate | >60% | Proxy for coaching quality and motivation |
| Session 3 self-rating improvement | >1.0 stars avg vs session 1 | Quantified progress |
| Month 2 retention | >50% | Product-market fit signal |
| Time to first coaching text received | 2–3 minutes | Core responsiveness signal |
| Time to coaching video received | 5–10 minutes | End-to-end pipeline reliability |
| Coaching video completion rate | >80% | Content quality signal |

---

## Relationship to Original Moment (Cookpad)

This is a clone built to understand and re-implement Moment's core experience.

Key differences from production Moment:
- No dedicated IoT camera (Cook Cam) — user uploads video from any device
- Google Cloud backend (Moment uses AWS)
- Gemini API for all AI (Moment uses custom-trained models + proprietary chef dataset)
- Web-first (Moment is mobile-native)

The coaching philosophy, user flow, dish structure, and coaching format are
modelled closely on Moment's production experience as documented through
product reviews, job postings, and a YouTube coaching video analysis.

See [`docs/architecture.md`](architecture.md) for a full technical comparison.

---

## Documents

| Document | Purpose |
|---|---|
| [`design.md`](design.md) | Data models, API, AI pipeline specification |
| [`architecture.md`](architecture.md) | System architecture, Moment vs clone comparison |
| [`ai_feasibility.md`](ai_feasibility.md) | Academic paper analysis, AI challenge feasibility |
| [`principal_engineers_analysis.md`](principal_engineers_analysis.md) | Analysis of Moment's engineering challenges |
