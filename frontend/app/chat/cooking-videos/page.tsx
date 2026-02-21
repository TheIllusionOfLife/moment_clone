"use client";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import type { MessagesResponse } from "@/types/api";
import { Skeleton } from "@/components/ui/skeleton";

export default function CookingVideosPage() {
  const { apiFetch } = useApi();
  const { data, isLoading } = useQuery<MessagesResponse>({
    queryKey: ["messages", "cooking_videos"],
    queryFn: () =>
      apiFetch<MessagesResponse>(
        "/api/chat/rooms/cooking_videos/messages/",
      ),
    refetchInterval: 30_000,
  });

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-xl font-bold text-zinc-900 mb-6">料理動画</h1>
      {isLoading ? (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : data?.messages.length === 0 ? (
        <p className="text-sm text-zinc-400">
          まだ動画はありません。
        </p>
      ) : (
        <div className="space-y-4">
          {data?.messages.map((msg) => (
            <div
              key={msg.id}
              className="rounded-lg border border-zinc-200 p-4"
            >
              {msg.text && (
                <p className="text-sm text-zinc-700 mb-3">{msg.text}</p>
              )}
              {msg.video_url && (
                <video
                  src={msg.video_url}
                  controls
                  className="w-full rounded-lg"
                />
              )}
              <p className="text-xs text-zinc-400 mt-2">
                {new Date(msg.created_at).toLocaleString("ja-JP")}
              </p>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
