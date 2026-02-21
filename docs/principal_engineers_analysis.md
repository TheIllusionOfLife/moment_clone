# What Cookpad's Principal Engineers Are Building

Analysis of the two principal AI engineering roles for moment, based on job descriptions,
recruiter posting, YouTube coaching video, screenshots, product manager interview, and
academic paper research.

---

## Principal Applied AI Engineer — Estimated Scope

### Core Mandate
> *"Work backward from the ideal learning experience to independently define the most critical problem"*

Owns the **video → insight → coaching script pipeline**.
The deliverable is not a chat response — it's a produced coaching video with a narration
script grounded in what the user's video actually shows.

---

### Project 1: Video Analysis Engine

The hardest unsolved problem. Produces structured cooking events from raw timelapse video:

```json
{
  "cooking_events": [
    { "t": "0:23", "event": "egg added", "state": "pan_temperature: too_high" },
    { "t": "0:41", "event": "rice added", "state": "egg: fully_cooked — ERROR" },
    { "t": "1:12", "event": "seasoning added", "state": "moisture: not_reduced" }
  ],
  "key_moment_timestamp": "0:41",
  "diagnosis": "egg fully cooked before rice addition causes clumping throughout"
}
```

**Approach (inferred)**:
- CHEF-VL-like dual-agent pattern (action agent + environment state agent)
- Custom CV layer for precision signals: heat level, doneness state, ingredient transformation
- 4-year proprietary chef coaching dataset provides training signal for domain-specific fine-tuning
- Bubble dynamics analysis (BubbleID pattern) for heat intensity estimation

**Academic grounding**:
- CHEF-VL (2025): dual-VLM achieves 80.92% kitchen action recognition — directly applicable
- BubbleID (2025): Mask R-CNN on bubble dynamics for heat estimation (AP50: 74.8%)
- Doneness classification (2025): ResNet-50 + CIELAB color space, 90.85% accuracy

---

### Project 2: Learner Analysis System (学び手解析)

A standalone longitudinal model that reads across all sessions and produces a structured
learning trajectory — distinct from per-session coaching. Mentioned explicitly in the
recruiter posting as one of Cookpad's three core AI products.

```json
{
  "skills_acquired": ["moisture_control"],
  "skills_developing": ["heat_management"],
  "recurring_mistakes": ["over-cooking_egg_before_combining"],
  "learning_velocity": "progressing",
  "next_focus": "oil_coating_technique",
  "ready_for_next_dish": false
}
```

This is what makes coaching feel like a real coach who remembers you across weeks.
It also drives dish progression decisions: when is the user ready to unlock dish 2?

---

### Project 3: Coaching Script Generator

Takes video analysis output + learner state + RAG (cooking principles knowledge base)
and produces two outputs:

**Output A — Structured coaching text** (delivered in Coaching chat room):
```
🍳 今回の問題点       ← root cause from video analysis
🍳 身につけるべきスキル ← principle from RAG + learner state
次回試すこと          ← single concrete action
✅ 成功のサイン        ← observable physical cue (sound, texture, visual)
```

**Output B — 2-part narration script** (for the coaching video):
```
Part 1: Core principle + diagnosis of this session
         (narrated over intro montage / full timelapse)

[PIVOT]: "動画を使ってそのポイントを見てみましょう"
         ("Let's look at that moment in the video")

Part 2: Narration synced to extracted clip at key_moment_timestamp
         References observable cues: sound ("シュワシュワ"), visual state
         Ends with the decisive rule
```

The obsession here (per recruiter post): coaching word endings, tone, every moment of
praise and every corrective framing are tuned obsessively — not written, engineered.

---

### Project 4: Task / Research Agents

Orchestration layer that determines *what* to focus on for each session before the
coaching script generator runs.

Example reasoning chain:
> "This user has done fried rice twice. Session 2 showed oil improvement but rice
> clumping persists. The highest-leverage focus for session 3 is rice moisture reduction.
> Relevant principle from knowledge base: [retrieved]. Pass to coaching script generator."

These are the "task/research agents" explicitly mentioned in the job description.

---

## Principal Conversational AI Engineer — Estimated Scope

### Core Mandate
> *"Design dialogue systems that maintain context across multiple user interactions"*

Owns everything **after the coaching video is delivered**, and the entire Help chat room.
The deliverable is a conversation that never breaks, never loses context, and always
feels like a coherent coaching relationship.

---

### Project 1: Coaching Chat Q&A System

After coaching delivery, users ask follow-up questions referencing their specific session.
The AI must answer in full context:

- *"You said to double the oil — but won't that make it greasy?"*
- *"At what point exactly should I add the rice?"*
- *"The sizzle sound you mentioned — what does it actually sound like?"*

Required context per turn:
- Full session video analysis output
- Coaching script that was delivered
- Learner state
- Full conversation history

The recruiter post calls out *"where conversation becomes unnatural"* and *"where context
retention collapses"* as the failure modes being obsessively tracked and fixed.
Breakdown cases — ambiguous questions, emotional frustration, off-topic questions —
are their active QA surface.

---

### Project 2: Voice Memo Processing Pipeline

User records a voice self-assessment after each cook. Converts audio into structured data
for the coaching script generator:

```
Audio: "I thought the egg was a bit oily, and I wasn't sure when to add the rice.
        The fried rice came out kind of wet."

→ {
    "self_ratings": { "texture": 2, "flavour": 3 },
    "identified_issues": ["oiliness", "moisture"],
    "questions": ["rice_addition_timing"],
    "emotional_state": "uncertain_but_engaged"
  }
```

The recruiter post cites "音声認識の誤差0.1%" (0.1% ASR error) as a detail they obsess
over. Generic STT fails on cooking vocabulary (だし, 炒める, フライパン, dish/technique
names mid-sentence). ASR is likely fine-tuned on cooking-domain vocabulary.

---

### Project 3: Onboarding Dialogue (~40 questions)

The type-quiz is not a static form — it's an adaptive conversational flow. If someone
says they've cooked for 10 years but can't make fried rice, the follow-up questions
change. The Conversational AI engineer owns the intent/entity extraction that turns
quiz responses into the initial learner profile written to the learner state system.

---

### Project 4: Context Management State Machine

The invisible infrastructure behind all chats. At any point the system knows:

```
{
  "current_dish": "fried_rice",
  "session_number": 2,
  "coaching_delivered": true,
  "last_user_message": "...",
  "last_ai_response": "...",
  "session_gap_days": 12,
  "context_risk": "high"   ← long gap, may need re-anchoring
}
```

The recruiter post explicitly names *"the moment when model's context retention collapses"*
as a failure mode they obsess over — this is a real engineering concern, not a UX note.

---

### Project 5: Help Chat Dialogue System

General support chat room handling:
- Technique questions outside current session context
- Scheduling / logistics questions (camera setup, session timing)
- Emotional support / motivation (user frustrated after session 2 failure)
- Out-of-scope escalation to human support team

Intent recognition + entity extraction + fallback/escalation routing.

---

## Combined Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  PRINCIPAL APPLIED AI ENGINEER owns:                        │
│                                                             │
│  User timelapse + voice memo                                │
│         ↓                                                   │
│  Video Analysis Engine                                      │
│  (CHEF-VL dual-agent + custom CV heat/doneness)             │
│         ↓                                                   │
│  Learner Analysis System  ←  longitudinal skill trajectory  │
│         ↓                                                   │
│  Task/Research Agent      ←  what to focus on this session  │
│         ↓                                                   │
│  Coaching Script Generator                                  │
│  (4-section text + 2-part narration script)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ coaching text + narration script
┌──────────────────────────▼──────────────────────────────────┐
│  PRINCIPAL CONVERSATIONAL AI ENGINEER owns:                  │
│                                                             │
│  Voice Memo Processing                                      │
│  (fine-tuned ASR + entity extraction → structured input)    │
│         ↓                                                   │
│  Coaching Chat Q&A                                          │
│  (multi-turn, session-aware, context state machine)         │
│         ↓                                                   │
│  Help Chat Dialogue                                         │
│  (intent recognition, fallback, human escalation)           │
│         ↓                                                   │
│  Onboarding Dialogue                                        │
│  (adaptive ~40-Q quiz → initial learner profile)            │
└─────────────────────────────────────────────────────────────┘
```

---

## The Researchers Cookpad Would Target

The 探索責任者 (Exploration Director) role searches papers, GitHub, and labs specifically
to find people like these — before competitors do. These are the highest-value profiles
based on paper research.

### Tier 1 — Immediate Targets

**Ruiqi Wang — Washington University in St. Louis** ★ Highest priority
- Lead author: CHEF-VL (2025)
- Team: WashU AI for Health Institute + Program in Occupational Therapy
  (original goal: helping cognitively impaired users follow cooking steps —
  Cookpad would be first to repurpose this for performance coaching)
- Expertise: Detecting sequencing errors in real-time on embedded hardware
- Status: **2025 Google PhD Fellow, finishing PhD → entering job market now**
- Unique signal: "The Mistake Catcher" — doesn't just recognise actions, recognises errors
- Cookpad approach: cold email referencing CHEF-VL Section 3.2 specifically,
  before Google's PhD recruiter sends a form email

**Yu Xiang — UT Dallas (formerly NVIDIA Research Robotics)**
- Co-author: CaptainCook4D (NeurIPS 2024)
- Creator of PoseCNN; understands 3D spatial geometry of kitchen environments
- Enables coaching at the level of: "heat is too high on the left side of the pan",
  "you are cutting too close to your fingers"
- NVIDIA Robotics background = production-grade, scalable perception — rare in food AI
- Status: Senior researcher, harder to recruit; conference approach (CVPR/ICCV) best

### Tier 2 — Strong Candidates

**Weiqing Min — Chinese Academy of Sciences (ICT)**
- Lead author: FoodSky (2024)
- Pioneer of "Food Computing" as a research field — practically invented it
- Built the model that passed the Chinese National Chef Examination (83.3%) and
  Dietetic Examination (91.2%), surpassing GPT-4o on culinary domain reasoning
- Specialises in multi-modal alignment of recipes to visuals + culinary knowledge graphs
- For Cookpad: the "culinary brain" behind the RAG knowledge base
- Status: Geography barrier (China-based), but research collaboration is possible

**Rohith Peddi — UT Dallas**
- Co-author: CaptainCook4D (NeurIPS 2024), same lab as Yu Xiang
- Focus: Neuro-Symbolic AI bridging raw video → logical reasoning
  ("user is chopping but recipe says dice")
- 2025 LinkedIn internship: industry-adjacent, actively recruitable
- For Cookpad: the reasoning layer connecting video observation to recipe compliance

**BubbleID Team — UIUC / Purdue (C. Dunlap, Ungjin Na, JunYoung Seo)**
- Paper: BubbleID (2025) — bubble interface tracking for smart cooking vessels
- Focus: detecting boiling/simmering/heat intensity via bubble dynamics
- Most overlooked profile: hardware-oriented, not a famous lab, not being recruited
  for cooking coaching by anyone — exactly the profile the recruiter post targets
- For Cookpad: the heat level detection module (the hardest CV problem in the pipeline)

### Full Author Map

| Researcher | Institution | Specialty | Recruitability |
|---|---|---|---|
| **Ruiqi Wang** | WashU | Error detection, embedded real-time CV | PhD finishing 2025 — prime window |
| **Yu Xiang** | UT Dallas (ex-NVIDIA) | 3D spatial perception, production CV | Senior, conference approach |
| **Weiqing Min** | CAS ICT, China | Food knowledge graphs, culinary LLM | Geography barrier, collaboration possible |
| **Rohith Peddi** | UT Dallas | Neuro-symbolic procedural reasoning | Junior, industry-ready |
| **BubbleID team** | UIUC/Purdue | Heat detection via bubble dynamics | Most overlooked, highest specificity |

### Why the CHEF-VL Origin Story Matters

The WashU team built CHEF-VL for **occupational therapy** — not cooking coaching.
This is the recruiter post insight in action:
> *"一見関係なさそうに見える分野の技術者でも、そのスキルこそが解決策になると見抜く"*
> "Even engineers from seemingly unrelated fields — recognising that their skill is
> exactly the solution."

A standard recruiter searching "cooking AI engineer" would never find Ruiqi Wang.
The 探索責任者 reading arXiv papers would.

---

## Their Active Hard Problems (as of early 2025)

The AI version launched October 2024. These roles are open now, which means these are
the problems not yet solved to their standard:

| Engineer | Current Hard Problem |
|---|---|
| Applied AI | Closing the precision gap: moving from qualitative heat assessment ("too hot") to actionable ("your pan was at excessive heat during the 0:23–0:41 window") |
| Applied AI | Making learner analysis accurate enough to reliably gate dish progression (when is the user genuinely ready for dish 2?) |
| Applied AI | Fine-grained hand/technique analysis — fingertip angle and grip were cited in the recruiter post as a detail worth engineering |
| Conversational AI | Conversation breakdown in coaching Q&A when users ask unexpected or emotionally loaded questions |
| Conversational AI | Context retention after long session gaps (user returns after 3 weeks — how to re-anchor without feeling like starting over) |
| Conversational AI | 0.1% ASR error on cooking-domain vocabulary in Japanese |

---

## Achievability for Our Clone (with Gemini API)

| Component | Their Approach | Our Approach | Gap |
|---|---|---|---|
| Video Analysis Engine | Custom CV + fine-tuned VLM | Single-agent structured analysis with Gemini 3 Flash Preview | Heat precision; hand pose |
| Learner Analysis | Standalone model on proprietary data | Structured Supabase PostgreSQL record + Gemini classification | Accuracy of skill acquisition detection |
| Task/Research Agents | Custom multi-agent | LangGraph + Gemini | Minimal gap |
| Coaching Script Generator | Fine-tuned LLM on chef data | Gemini 3 Flash Preview + RAG + prompt engineering | Coaching tone precision |
| Voice Memo Processing | Fine-tuned ASR + entity extraction | Cloud STT + phrase hints + Gemini extraction | ASR on rare cooking terms |
| Coaching Chat Q&A | Custom dialogue system + state machine | Gemini + Supabase session context | Breakdown handling |
| Onboarding Dialogue | Custom adaptive quiz | Gemini-driven flow | Minimal gap |
| Context State Machine | Custom | Supabase PostgreSQL + session doc | Long-gap re-anchoring |
