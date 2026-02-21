import { http, HttpResponse } from "msw";

const API_BASE = "http://localhost:8000";

const mockUser = {
  id: 1,
  clerk_user_id: "user_test",
  email: "test@example.com",
  first_name: "Test",
  onboarding_done: true,
  subscription_status: "free",
  learner_profile: null,
  created_at: "2024-01-01T00:00:00Z",
};

const mockDishes = [
  {
    id: 1,
    slug: "chahan",
    name_ja: "チャーハン",
    name_en: "Fried Rice",
    description_ja: "炒飯",
    principles: ["水分コントロール"],
    transferable_to: [],
    month_unlocked: 1,
    order: 1,
    progress: {
      status: "not_started",
      started_at: null,
      completed_at: null,
    },
  },
  {
    id: 2,
    slug: "steak",
    name_ja: "ビーフステーキ",
    name_en: "Beef Steak",
    description_ja: "ステーキ",
    principles: ["火加減"],
    transferable_to: [],
    month_unlocked: 1,
    order: 2,
    progress: {
      status: "in_progress",
      started_at: "2024-01-01T00:00:00Z",
      completed_at: null,
    },
  },
  {
    id: 3,
    slug: "pomodoro",
    name_ja: "ポモドーロ",
    name_en: "Pomodoro",
    description_ja: "トマトパスタ",
    principles: ["酸味のバランス"],
    transferable_to: [],
    month_unlocked: 1,
    order: 3,
    progress: {
      status: "completed",
      started_at: "2024-01-01T00:00:00Z",
      completed_at: "2024-02-01T00:00:00Z",
    },
  },
];

const mockSession = {
  id: 1,
  user_id: 1,
  dish_id: 1,
  session_number: 1,
  status: "processing" as const,
  raw_video_url: null,
  voice_memo_url: null,
  self_ratings: {},
  voice_transcript: null,
  structured_input: {},
  video_analysis: {},
  coaching_text: null,
  coaching_text_delivered_at: null,
  narration_script: {},
  coaching_video_url: null,
  pipeline_error: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockMessages = {
  page: 1,
  page_size: 50,
  messages: [
    {
      id: 1,
      sender: "ai" as const,
      text: "こんにちは！AIコーチです。",
      video_url: null,
      metadata: {},
      session_id: null,
      created_at: "2024-01-01T00:00:00Z",
    },
  ],
};

export const handlers = [
  http.get(`${API_BASE}/api/auth/me/`, () => HttpResponse.json(mockUser)),
  http.patch(`${API_BASE}/api/auth/me/`, () =>
    HttpResponse.json({ ...mockUser, onboarding_done: true }),
  ),
  http.get(`${API_BASE}/api/dishes/`, () => HttpResponse.json(mockDishes)),
  http.get(`${API_BASE}/api/dishes/:slug/`, ({ params }) =>
    HttpResponse.json(
      mockDishes.find((d) => d.slug === params.slug) ?? mockDishes[0],
    ),
  ),
  http.post(`${API_BASE}/api/sessions/`, () =>
    HttpResponse.json(mockSession, { status: 201 }),
  ),
  http.get(`${API_BASE}/api/sessions/`, () => HttpResponse.json([])),
  http.get(`${API_BASE}/api/sessions/:id/`, () =>
    HttpResponse.json(mockSession),
  ),
  http.post(`${API_BASE}/api/sessions/:id/upload/`, () =>
    HttpResponse.json({ ...mockSession, status: "uploaded" }),
  ),
  http.post(`${API_BASE}/api/sessions/:id/voice-memo/`, () =>
    HttpResponse.json(mockSession),
  ),
  http.patch(`${API_BASE}/api/sessions/:id/ratings/`, () =>
    HttpResponse.json(mockSession),
  ),
  http.get(`${API_BASE}/api/chat/rooms/coaching/messages/`, () =>
    HttpResponse.json(mockMessages),
  ),
  http.get(`${API_BASE}/api/chat/rooms/cooking_videos/messages/`, () =>
    HttpResponse.json({ ...mockMessages, messages: [] }),
  ),
  http.post(`${API_BASE}/api/chat/rooms/coaching/messages/`, () =>
    HttpResponse.json(
      {
        id: 99,
        sender: "user",
        text: "test",
        metadata: {},
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    ),
  ),
];
