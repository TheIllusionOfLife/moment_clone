# AI Feasibility Analysis — What Moment's Principal Engineers Solve vs. What Gemini API Can Do

## Context

Moment hires Principal Applied AI Engineers and Principal Conversational AI Engineers
to solve hard AI problems in cooking coaching. This document assesses each challenge
and whether it's achievable via Gemini API (prompt engineering, RAG, or post-training)
vs. requiring custom model development.

---

## Principal Applied AI Engineer — Challenge Analysis

### Challenge 1: Heat Level Detection from Video
> *"An elite coach can instantly discern from video the heat level, early signs of failure,
> and the appropriate corrective actions"*

**What they're solving**: A custom CV model that reliably classifies heat level
(too low / correct / too high) from visual cues — oil shimmer, smoke, bubble rate,
color change — without explicit temperature sensors.

**With Gemini API?**
- Gemini can describe what it sees: *"the oil appears to be smoking, indicating it is very hot"*
- Cannot give calibrated precision ("this is 180°C, you need 160°C")
- Detects obvious failure (burning, smoking) but may miss **early** signs before they're visually dramatic
- **Verdict: ~65%. Good enough for coaching ("your heat looks too high here"), not good enough for real-time precision intervention.**

---

### Challenge 2: Fundamental Cooking Video Understanding
> *"Solving fundamental challenges in understanding cooking videos"*

The specific hardness: steam, lighting variation, ingredient transformation
(raw → cooked is a continuous visual change), and temporal ordering all matter.

**With Gemini API?**
- Gemini's native video understanding handles temporal context well
- Steam and lighting variation do degrade accuracy — a real challenge for any vision model
- Temporal ordering ("did they add salt before or after the water boiled?") Gemini handles well with careful prompting
- **Verdict: ~75%. Genuinely hard for any model without domain-specific training. Gemini gets usable coaching quality, not expert-level precision.**

---

### Challenge 3: Multimodal Decision-Making (Video + Audio + Text)
> *"Designing multimodal (video, audio, text) decision-making models"*

**With Gemini API?**
- Gemini 3 Flash Preview is natively multimodal
- Feed: timelapse video + user voice memo transcript + session history = single unified analysis call
- **Verdict: ~95%. Almost entirely solved by the API. The "design" challenge is prompt architecture, not model capability.**

---

### Challenge 4: Coaching Logic with Conversational Memory + Learning State
> *"Designing coaching logic that takes conversational memory and learning state into account"*

**With Gemini API?**
- The LLM doesn't need to remember — **you inject the state**
- Firestore holds the learner model: `{ skills_developing: [...], recurring_mistakes: [...], session_history: [...] }`
- RAG retrieves relevant past sessions at coaching time
- Gemini generates coaching conditioned on all of that context
- **Verdict: ~95%. This is a data modelling + retrieval problem, not a model problem. Fully solvable.**

---

### Challenge 5: Task / Research Agents
> *"Designing and implementing task/research agents"*

**With Gemini API?**
- Multi-agent orchestration is a framework + prompt engineering problem
- LangGraph or Google ADK handles agent graph wiring; Gemini drives each agent's reasoning
- **Verdict: ~95%. Fully solvable with current tooling.**

---

## Principal Conversational AI Engineer — Challenge Analysis

### Challenge 6: Intent Recognition + Entity Extraction
> *"Implement robust systems for intent recognition, entity extraction, and context management"*

**With Gemini API?**
- Gemini structured outputs (JSON mode) handles this cleanly
- e.g. `{ intent: "technique_question", entity: "oil_amount", session_ref: "session_1" }`
- **Verdict: ~95%.**

---

### Challenge 7: Fallback + Escalation to Human Support
> *"Develop fallback mechanisms and escalation paths for handling ambiguous inputs and edge cases"*

**With Gemini API?**
- Gemini can output a confidence signal or flag uncertainty in structured output
- Route to human support queue when confidence < threshold or topic is outside cooking domain
- **Verdict: ~90%. The logic is straightforward; the hard part is calibrating the threshold, not the AI.**

---

### Challenge 8: Personalization Across Sessions
> *"Build personalization capabilities into conversations based on user preferences and history"*

**With Gemini API?**
- Fully a context injection problem — Firestore learner state + past session summaries in prompt
- **Verdict: ~95%.**

---

## Summary Table

| Challenge | Gemini API Feasibility | Gap |
|---|---|---|
| Heat level detection | 65% | Needs domain-specific fine-tuning for precision |
| Early failure sign detection | 60% → **80%** | CHEF-VL pattern replicable with Gemini (see papers) |
| Cooking video understanding (steam, lighting) | 75% | Heavy steam needs audio/thermal fusion |
| Multimodal (video+audio+text) fusion | 95% | Almost free with Gemini native multimodal |
| Coaching logic + learning state | 95% | Data design problem, not a model problem |
| Multi-agent orchestration | 95% | Framework + prompt problem |
| Intent recognition + entity extraction | 95% | Structured output solves this |
| Fallback / escalation | 90% | Threshold calibration, not AI |
| Personalization across sessions | 95% | Context injection + Firestore |

---

## Academic Paper Evidence (2019–2025)

### Heat Level Detection

**"Construction of an intelligent recognition system for cooking doneness" (2025)**
- ResNet-50 + CIELAB color space analysis
- 90.85% accuracy for doneness classification (browned, caramelised, etc.)
- Color transformation is highly correlated with thermal state
- **Verdict**: State classification (low/medium/high/too high) is achievable.
  Exact temperature estimation is not — needs custom regression on bubble dynamics.

**"BubbleID: A Deep Learning Framework for Bubble Interface Dynamics Analysis" (2025)**
- Authors: C. Dunlap, Ungjin Na, JunYoung Seo — UIUC / Purdue
- Built for smart cooking vessels — detecting boiling/simmering via bubble tracking
- Mask R-CNN tracking bubble departure rate, morphology, velocity
- AP50 of 74.8% for bubble detection; 99.27% in controlled conditions
- **Verdict**: Requires custom CV. Not achievable with Gemini API alone.
  Qualitative heat assessment ("oil is smoking") is achievable; calibrated temp is not.
- **Recruitment note**: Most overlooked team in cooking AI — hardware-oriented,
  not a famous lab. Exactly the profile Cookpad's探索責任者 would surface from arXiv.

---

### Early Failure / Anomaly Detection

**"CHEF-VL: Detecting Cognitive Sequencing Errors in Cooking with Vision-Language Models" (2025)**
- Authors: Ruiqi Wang, Peiqi Gao, Patrick Lynch, Tingjun Liu, Yejin Lee,
  Carolyn M. Baum, Lisa Tabor Connor, Chenyang Lu
- Institution: Washington University in St. Louis — AI for Health Institute +
  Program in Occupational Therapy
- Original goal: helping cognitively impaired users follow cooking steps
  (repurposable for performance coaching — exactly the "unrelated field" insight)
- Dual-VLM architecture: one for Human Action Recognition, one for environment state
  ("stove is on", "pot is empty"), compared against a symbolic recipe graph
- 80.92% action recognition accuracy in kitchen environments
- **Verdict**: HIGH feasibility with Gemini API. Directly replicable without retraining.
  This is the pattern we should adopt for procedural error detection.
- **Recruitment note**: Lead author Ruiqi Wang is a 2025 Google PhD Fellow finishing
  his PhD — prime recruitment window. Real-time inference on embedded hardware.

**"CaptainCook4D: A Dataset for Understanding Errors in Procedural Activities" (NeurIPS 2024)**
- Authors: Rohith Peddi, Yu Xiang (ex-NVIDIA Research Robotics), Vibhav Gogate — UT Dallas
- 4D egocentric video dataset of procedural cooking errors
- Action-State Merging for procedural error detection
- **Verdict**: HIGH for high-level procedural errors; moderate for subtle timing errors.
- **Dataset value**: Most directly applicable dataset for training our video analysis model.
- **Recruitment note**: Peddi (junior, 2025 LinkedIn intern) and Xiang (senior, ex-NVIDIA)
  are at the same institution — could be approached as a pair.

---

### Cooking Under Challenging Visual Conditions (Steam, Lighting)

**"Multi-Modal Hand-to-Mouth Gesture Recognition" (2023)**
- RGB + Thermal sensor fusion to see through steam/smoke
- **Verdict**: Custom hardware required (thermal camera). Not applicable to us.
  However: audio fusion is the software-accessible equivalent.

**"Robust Cooking Activity Recognition using Sound and Motion" (2020/2022)**
- Audio CNN classifying sounds (frying, simmering, steaming) as non-visual state check
- ~80% general action recognition; higher with multimodal fusion
- **Verdict**: Gemini's native audio capability partially covers this.
  User's voice memo + any ambient cooking sounds can partially compensate for
  steam-occluded video frames.

---

### Foundation Models on Cooking Domain

**"FoodSky" (2024)**
- Authors: Weiqing Min, Shuqiang Jiang — Chinese Academy of Sciences (ICT)
- Pioneer of "Food Computing" as a research field
- 83.3% on Chinese National Chef Examination, 91.2% on Dietetic Examination
- Surpasses GPT-4o on domain-specific culinary reasoning
- **Verdict**: General VLMs can be strongly primed for culinary domains.
  RAG + domain-specific prompting brings Gemini very close.
- **Dataset/knowledge value**: Min's culinary knowledge graph work is the
  most mature foundation for building our RAG cooking principles knowledge base.

**"FoodLMM: A Versatile Food Assistant" (2024)**
- Authors: Yuehao Yin, Jingjing Chen, C. Ngo — Fudan University / SMU
- LLaVA + SAM fine-tuned on culinary datasets
- Multimodal food recognition, segmentation, recipe generation
- **Verdict**: Fine-tuning on cooking data gives meaningful gains. Achievable on Vertex AI.

---

## Revised Feasibility After Literature Review

| Challenge | Before Papers | After Papers | Key Finding |
|---|---|---|---|
| Heat level detection (qualitative) | 65% | **75%** | Color/smoke cues work; calibrated temp does not |
| Heat level detection (precise) | 65% | **25%** | Needs bubble regression model (BubbleID) |
| Early failure / procedural errors | 60% | **80%** | CHEF-VL pattern works with VLM API directly |
| Steam/smoke occlusion | 75% | **55%** | Thermal camera needed; audio partially compensates |
| Culinary domain reasoning | 85% | **90%** | FoodSky shows VLMs strong with domain priming |

---

## The 20% Gap — Revised

The gap is now more precisely located:

| Hard (needs custom CV) | Achievable (Gemini API) |
|---|---|
| Calibrated temperature from bubble dynamics | Qualitative heat state (low/med/high) |
| Heavy steam occlusion (thermal camera) | Audio-based activity recognition |
| Fingertip/hand pose analysis | Procedural error detection (CHEF-VL pattern) |
| Precise timing detection ("30s before burning") | High-level failure detection (burning, wrong order) |

---

## Implications for Our Clone

**We can match Moment on coaching logic from day one.**
The key upgrade from the paper research: **procedural error detection** is more
achievable than originally estimated — the CHEF-VL dual-VLM pattern is directly
replicable with Gemini.

| Layer | Approach | Confidence |
|---|---|---|
| Coaching script quality | Prompt engineering + RAG | High |
| Learner state + personalization | Firestore + context injection | High |
| Dialogue management | Gemini structured outputs | High |
| Qualitative heat assessment | Gemini video prompting + color/smoke cues | Medium-High |
| Procedural error detection | CHEF-VL dual-VLM pattern with Gemini | Medium-High |
| Steam/smoke robustness | Audio fusion (user voice memo + ambient sound) | Medium |
| Precise heat calibration | Not in MVP — V2 with custom model | Low (V2 only) |
| Fingertip/hand pose | Not in MVP — V2 with MediaPipe | Low (V2 only) |

**Path to closing the remaining gap:**
1. Collect session data (video + coaching outcomes + user ratings) from real users
2. Fine-tune on accumulated data using Vertex AI (start with doneness classification)
3. The proprietary dataset we build from real sessions becomes our own competitive moat

The principal engineers at Moment are not training novel architectures —
they're designing right abstractions around foundation models, adopting patterns
from papers like CHEF-VL, and closing precision gaps with domain-specific fine-tuning.
That is exactly what we will do.
