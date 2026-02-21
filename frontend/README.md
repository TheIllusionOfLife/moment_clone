# Frontend — moment-clone

Next.js App Router frontend for the Moment clone PWA.

## Stack

- Next.js (App Router)
- TypeScript
- Tailwind CSS + shadcn/ui
- TanStack Query
- Biome
- bun

## Prerequisites

- bun installed
- Backend running at `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`)
- Clerk publishable key

## Setup

```bash
cd frontend
bun install
```

Set `frontend/.env.local`:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Run

```bash
cd frontend
bun dev
```

Open `http://localhost:3000`.

## Quality Checks

```bash
cd frontend
bunx biome check --write .
```

## Main App Routes

- `/` landing page
- `/onboarding` learner profile quiz
- `/dashboard` dish selection + progress
- `/dishes/[slug]` dish details + session history
- `/sessions/new/[slug]` upload flow (video + voice memo + ratings)
- `/sessions/[id]` session detail + coaching output
- `/chat/cooking-videos` cooking videos room
- `/chat/coaching` coaching room + Q&A

## Product Notes

- Coaching delivery is tiered: text first (~2–3 min), video follows (~5–10 min).
- Coaching and chat are Japanese-first for MVP.
- Authentication uses Clerk on frontend and JWT verification on backend.
