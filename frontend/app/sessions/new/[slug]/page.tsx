"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import type { CookingSession } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";

const MAX_VIDEO_MB = 500;

export default function NewSessionPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const { apiFetch, apiUpload } = useApi();

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [ratings, setRatings] = useState({
    appearance: 3,
    taste: 3,
    texture: 3,
    aroma: 3,
  });
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionCreated = useRef(false);

  // Create session on mount
  useEffect(() => {
    if (sessionCreated.current) return;
    sessionCreated.current = true;
    apiFetch<CookingSession>("/api/sessions/", {
      method: "POST",
      body: JSON.stringify({ dish_slug: slug }),
    })
      .then((s) => setSessionId(s.id))
      .catch((e: Error) => setError(e.message));
  }, [slug, apiFetch]);

  function handleVideoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (file && file.size > MAX_VIDEO_MB * 1024 * 1024) {
      setError(`動画ファイルは${MAX_VIDEO_MB}MB以下にしてください`);
      return;
    }
    setError(null);
    setVideoFile(file);
  }

  async function handleUpload() {
    if (!videoFile || !sessionId) return;
    setUploading(true);
    setError(null);

    try {
      const videoForm = new FormData();
      videoForm.append("video", videoFile);
      await apiUpload<CookingSession>(
        `/api/sessions/${sessionId}/upload/`,
        videoForm,
      );
      setUploadProgress(50);

      if (audioFile) {
        const audioForm = new FormData();
        audioForm.append("audio", audioFile);
        await apiUpload<CookingSession>(
          `/api/sessions/${sessionId}/voice-memo/`,
          audioForm,
        );
      }
      setUploadProgress(80);

      await apiFetch(`/api/sessions/${sessionId}/ratings/`, {
        method: "PATCH",
        body: JSON.stringify(ratings),
      });
      setUploadProgress(100);
      router.push(`/sessions/${sessionId}`);
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "アップロードに失敗しました",
      );
      setUploading(false);
    }
  }

  const ratingLabels = [
    { key: "appearance" as const, label: "見た目" },
    { key: "taste" as const, label: "味" },
    { key: "texture" as const, label: "食感" },
    { key: "aroma" as const, label: "香り" },
  ];

  return (
    <main className="max-w-xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-zinc-900 mb-6">
        料理動画をアップロード
      </h1>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-6">
        {/* Video upload */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">料理動画 *</CardTitle>
          </CardHeader>
          <CardContent>
            <input
              type="file"
              accept="video/mp4,video/quicktime"
              onChange={handleVideoChange}
              disabled={uploading}
              className="block w-full text-sm text-zinc-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200"
            />
            <p className="text-xs text-zinc-400 mt-2">
              MP4またはMOV形式、最大{MAX_VIDEO_MB}MB
            </p>
          </CardContent>
        </Card>

        {/* Voice memo (optional) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              自己評価の音声メモ（任意）
            </CardTitle>
          </CardHeader>
          <CardContent>
            <input
              type="file"
              accept="audio/*"
              onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
              disabled={uploading}
              className="block w-full text-sm text-zinc-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200"
            />
          </CardContent>
        </Card>

        {/* Star ratings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">自己評価（任意）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {ratingLabels.map(({ key, label }) => (
              <div key={key} className="flex items-center justify-between">
                <Label className="w-16">{label}</Label>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((v) => (
                    <button
                      type="button"
                      key={v}
                      onClick={() =>
                        setRatings((r) => ({ ...r, [key]: v }))
                      }
                      className={`text-xl ${v <= ratings[key] ? "text-amber-400" : "text-zinc-200"}`}
                      disabled={uploading}
                    >
                      ★
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {uploading && (
          <div>
            <p className="text-sm text-zinc-600 mb-2">
              アップロード中...
            </p>
            <Progress value={uploadProgress} />
          </div>
        )}

        <Button
          className="w-full"
          disabled={!videoFile || uploading || !sessionId}
          onClick={handleUpload}
        >
          {uploading
            ? "アップロード中..."
            : "アップロードしてAI分析を開始"}
        </Button>
      </div>
    </main>
  );
}
