export type SessionStatus =
  | "pending_upload"
  | "uploaded"
  | "processing"
  | "text_ready"
  | "completed"
  | "failed";

export interface User {
  id: number;
  clerk_user_id: string;
  email: string;
  first_name: string;
  onboarding_done: boolean;
  subscription_status: string;
  learner_profile: Record<string, unknown> | null;
  created_at: string;
}

export interface DishProgress {
  status: "not_started" | "in_progress" | "completed";
  started_at: string | null;
  completed_at: string | null;
}

export interface Dish {
  id: number;
  slug: string;
  name_ja: string;
  name_en: string;
  description_ja: string;
  principles: string[];
  transferable_to: string[];
  month_unlocked: number;
  order: number;
  progress: DishProgress;
}

export interface CoachingText {
  mondaiten: string;
  skill: string;
  next_action: string;
  success_sign: string;
}

export interface CookingSession {
  id: number;
  user_id: number;
  dish_id: number;
  session_number: number;
  status: SessionStatus;
  raw_video_url: string | null;
  voice_memo_url: string | null;
  self_ratings: Record<string, number> | null;
  voice_transcript: string | null;
  structured_input: Record<string, unknown> | null;
  video_analysis: Record<string, unknown> | null;
  coaching_text: CoachingText | null;
  coaching_text_delivered_at: string | null;
  narration_script: Record<string, unknown> | null;
  coaching_video_url: string | null;
  pipeline_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  sender: "user" | "ai";
  text: string | null;
  video_url: string | null;
  metadata: Record<string, unknown>;
  session_id: number | null;
  created_at: string;
}

export interface MessagesResponse {
  page: number;
  page_size: number;
  messages: Message[];
}

export interface ChatRoom {
  id: number;
  room_type: "coaching" | "cooking_videos";
  created_at: string;
}
