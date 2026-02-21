"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import type { Message, MessagesResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";

export default function CoachingChatPage() {
  const { apiFetch } = useApi();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [waitingForReply, setWaitingForReply] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useQuery<MessagesResponse>({
    queryKey: ["messages", "coaching"],
    queryFn: () =>
      apiFetch<MessagesResponse>("/api/chat/rooms/coaching/messages/"),
    refetchInterval: waitingForReply ? 3_000 : 30_000,
  });

  const messages = data?.messages ?? [];

  useEffect(() => {
    if (waitingForReply && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg?.sender === "ai") {
        setWaitingForReply(false);
      }
    }
  }, [messages, waitingForReply]);

  const sendMutation = useMutation({
    mutationFn: (text: string) =>
      apiFetch<Message>("/api/chat/rooms/coaching/messages/", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    onMutate: async (text) => {
      await queryClient.cancelQueries({ queryKey: ["messages", "coaching"] });
      const previous = queryClient.getQueryData<MessagesResponse>(["messages", "coaching"]);
      const optimistic: Message = {
        id: -Date.now(),
        sender: "user",
        text,
        video_url: null,
        metadata: {},
        session_id: null,
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData<MessagesResponse>(
        ["messages", "coaching"],
        (old) =>
          old
            ? { ...old, messages: [...old.messages, optimistic] }
            : old,
      );
      setInput("");
      setWaitingForReply(true);
      setTimeout(
        () => bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
        100,
      );
      return { previous };
    },
    onError: (_err, _text, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["messages", "coaching"], context.previous);
      }
      setWaitingForReply(false);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", "coaching"] });
    },
  });

  function handleSend() {
    const text = input.trim();
    if (!text || sendMutation.isPending) return;
    sendMutation.mutate(text);
  }

  return (
    <main
      className="max-w-2xl mx-auto px-4 py-6 flex flex-col"
      style={{ minHeight: "calc(100vh - 73px)" }}
    >
      <h1 className="text-xl font-bold text-zinc-900 mb-4">AIコーチ</h1>

      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                    msg.sender === "user"
                      ? "bg-zinc-900 text-white"
                      : "bg-zinc-100 text-zinc-800"
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
            {waitingForReply && (
              <div className="flex justify-start">
                <div className="bg-zinc-100 rounded-2xl px-4 py-2 text-sm text-zinc-500">
                  AIコーチが返答中...
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2 items-end">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="質問や感想を入力..."
          rows={2}
          className="flex-1 resize-none"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <Button
          onClick={handleSend}
          disabled={!input.trim() || sendMutation.isPending}
        >
          送信
        </Button>
      </div>
    </main>
  );
}
