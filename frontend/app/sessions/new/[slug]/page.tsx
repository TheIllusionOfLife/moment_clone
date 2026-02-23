"use client";
import { useState } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

const MAX_VIDEO_MB = 500;
const isFree = (slug: string) => slug === "free";

export default function NewSessionPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const { apiFetch } = useApi();

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [customDishName, setCustomDishName] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [memoText, setMemoText] = useState("");
  const [ratings, setRatings] = useState({
    appearance: 3,
    taste: 3,
    texture: 3,
    aroma: 3,
  });
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

      // Get a signed GCS PUT URL (bypasses Cloud Run 32 MB limit)
      const contentType = videoFile.type || "video/mp4";
      const { upload_url, gcs_path } = await apiFetch<{
        upload_url: string;
        gcs_path: string;
      }>(`/api/sessions/${sid}/upload-url/`, {
        method: "POST",
        body: JSON.stringify({ content_type: contentType }),
      });

      // Upload directly to GCS
      const gcsRes = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": contentType },
        body: videoFile,
      });
      if (!gcsRes.ok) throw new Error(`GCS upload failed: ${gcsRes.status}`);

      // Confirm upload to backend — triggers pipeline
      await apiFetch<CookingSession>(`/api/sessions/${sid}/confirm-upload/`, {
        method: "POST",
        body: JSON.stringify({ gcs_path }),
      });
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
        {/* Custom dish name — free-choice only */}
        {isFree(slug) && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">料理名 *</CardTitle>
            </CardHeader>
            <CardContent>
              <Input
                placeholder="例: 鶏の唐揚げ、ナポリタン..."
                value={customDishName}
                onChange={(e) => setCustomDishName(e.target.value)}
                disabled={uploading}
              />
            </CardContent>
          </Card>
        )}

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

        {/* Self-assessment text (replaces audio file upload) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              自己評価のコメント（任意）
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="今回の料理の感想や反省点を自由に書いてください。AIコーチがフィードバックに活用します。"
              value={memoText}
              onChange={(e) => setMemoText(e.target.value)}
              disabled={uploading}
              rows={4}
            />
          </CardContent>
        </Card>

        {/* Star ratings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">自己採点（任意）</CardTitle>
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
                      aria-label={`${label} ${v}点`}
                      aria-pressed={v <= ratings[key]}
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
          disabled={!videoFile || uploading || (isFree(slug) && !customDishName.trim())}
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
