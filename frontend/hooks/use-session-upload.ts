"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import type { CookingSession } from "@/types/api";

type Ratings = {
  appearance: number;
  taste: number;
  texture: number;
  aroma: number;
};

const isFree = (slug: string) => slug === "free";

export function useSessionUpload(slug: string) {
  const router = useRouter();
  const { apiFetch, apiUpload } = useApi();

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(
    videoFile: File | null,
    customDishName: string,
    memoText: string,
    ratings: Ratings,
  ) {
    if (!videoFile) return;
    if (isFree(slug) && !customDishName.trim()) {
      setError("料理名を入力してください");
      return;
    }
    setUploading(true);
    setError(null);

    try {
      let sid = sessionId;
      if (!sid) {
        const body: { dish_slug: string; custom_dish_name?: string } = {
          dish_slug: slug,
        };
        if (isFree(slug)) body.custom_dish_name = customDishName.trim();
        const session = await apiFetch<CookingSession>("/api/sessions/", {
          method: "POST",
          body: JSON.stringify(body),
        });
        sid = session.id;
        setSessionId(sid);
      }

      const videoForm = new FormData();
      videoForm.append("video", videoFile);
      await apiUpload<CookingSession>(
        `/api/sessions/${sid}/upload/`,
        videoForm,
      );
      setUploadProgress(40);

      if (memoText.trim()) {
        await apiFetch(`/api/sessions/${sid}/memo-text/`, {
          method: "POST",
          body: JSON.stringify({ text: memoText.trim() }),
        });
      }
      setUploadProgress(70);

      await apiFetch(`/api/sessions/${sid}/ratings/`, {
        method: "PATCH",
        body: JSON.stringify(ratings),
      });
      setUploadProgress(100);
      router.push(`/sessions/${sid}`);
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "アップロードに失敗しました",
      );
      setUploadProgress(0);
      setUploading(false);
    }
  }

  return {
    uploading,
    uploadProgress,
    error,
    setError,
    handleUpload,
  };
}
