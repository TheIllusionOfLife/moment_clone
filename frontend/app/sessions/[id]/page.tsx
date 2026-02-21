"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import type { CookingSession } from "@/types/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";

function CoachingTextSection({
  ct,
}: { ct: NonNullable<CookingSession["coaching_text"]> }) {
  const sections = [
    { key: "mondaiten" as const, title: "今回の課題点" },
    { key: "skill" as const, title: "身につけるスキル" },
    { key: "next_action" as const, title: "次回のアクション" },
    { key: "success_sign" as const, title: "成功のサイン" },
  ];
  return (
    <div className="space-y-4">
      {sections.map(({ key, title }) => (
        <Card key={key}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-zinc-600">
              {title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-800 whitespace-pre-wrap">
              {ct[key]}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { apiFetch } = useApi();

  const { data: session, isLoading, isError, error } = useQuery<CookingSession>({
    queryKey: ["session", id],
    queryFn: () => apiFetch<CookingSession>(`/api/sessions/${id}/`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 10_000;
    },
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <Alert variant="destructive">
          <AlertDescription>
            セッションの読み込みに失敗しました:{" "}
            {error instanceof Error ? error.message : "不明なエラー"}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-zinc-900 mb-6">
        セッション {session?.session_number} の結果
      </h1>

      {session?.status === "failed" && (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>
            エラーが発生しました:{" "}
            {session.pipeline_error ?? "不明なエラー"}
          </AlertDescription>
        </Alert>
      )}

      {(session?.status === "uploaded" ||
        session?.status === "processing") && (
        <Card className="mb-6">
          <CardContent className="py-8 text-center">
            <div className="inline-block w-8 h-8 border-2 border-zinc-300 border-t-zinc-900 rounded-full animate-spin mb-4" />
            <p className="text-zinc-600">
              AI分析中... 約2〜3分お待ちください
            </p>
          </CardContent>
        </Card>
      )}

      {session?.coaching_text && (
        <div className="mb-6">
          <h2 className="text-base font-semibold text-zinc-800 mb-3">
            AIコーチからのフィードバック
          </h2>
          <CoachingTextSection ct={session.coaching_text} />
        </div>
      )}

      {session?.status === "text_ready" && (
        <Card className="mb-6">
          <CardContent className="py-6 text-center">
            <div className="inline-block w-6 h-6 border-2 border-zinc-300 border-t-zinc-900 rounded-full animate-spin mb-3" />
            <p className="text-sm text-zinc-500">
              動画制作中... 約5〜10分
            </p>
          </CardContent>
        </Card>
      )}

      {session?.coaching_video_url && (
        <div className="mb-6">
          <h2 className="text-base font-semibold text-zinc-800 mb-3">
            コーチング動画
          </h2>
          <video
            src={session.coaching_video_url}
            controls
            aria-label="コーチング動画"
            className="w-full rounded-lg border border-zinc-200"
          />
        </div>
      )}
    </main>
  );
}
