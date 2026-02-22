"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import type { CookingSession, Dish } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const STATUS_LABEL: Record<string, string> = {
  pending_upload: "アップロード待ち",
  uploaded: "処理中",
  processing: "AI分析中",
  text_ready: "テキスト完了",
  completed: "完了",
  failed: "エラー",
};

export default function DishDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { apiFetch } = useApi();

  const { data: dish, isLoading: dishLoading, isError: dishError } = useQuery<Dish>({
    queryKey: ["dish", slug],
    queryFn: () => apiFetch<Dish>(`/api/dishes/${slug}/`),
    enabled: !!slug,
  });

  const { data: sessions, isLoading: sessionsLoading, isError: sessionsError } = useQuery<
    CookingSession[]
  >({
    queryKey: ["sessions", slug],
    queryFn: () =>
      apiFetch<CookingSession[]>(`/api/sessions/?dish_slug=${slug}`),
    enabled: !!slug,
  });

  const canStartNew =
    Array.isArray(sessions) &&
    (slug === "free" || sessions.length < 3);
  const isLoading = dishLoading || sessionsLoading;

  if (isLoading)
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <Skeleton className="h-64" />
      </div>
    );

  if (dishError || sessionsError)
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <p className="text-sm text-red-600">データの読み込みに失敗しました。</p>
      </div>
    );

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-zinc-900 mb-1">
        {dish?.name_ja}
      </h1>
      <p className="text-zinc-500 mb-6">{dish?.description_ja}</p>

      {dish?.principles && dish.principles.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-zinc-700 mb-2">
            学べる料理の原則
          </h2>
          <ul className="list-disc list-inside space-y-1">
            {dish.principles.map((p, i) => (
              <li key={i} className="text-sm text-zinc-600">
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}

      <h2 className="text-sm font-semibold text-zinc-700 mb-3">
        セッション履歴
      </h2>
      <div className="space-y-3 mb-6">
        {sessions && sessions.length > 0 ? (
          sessions.map((s) => (
            <Card key={s.id}>
              <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  {s.custom_dish_name
                    ? `${s.custom_dish_name} — セッション ${s.session_number}`
                    : `セッション ${s.session_number}`}
                </CardTitle>
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="text-xs">
                    {STATUS_LABEL[s.status] ?? s.status}
                  </Badge>
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/sessions/${s.id}`}>詳細</Link>
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))
        ) : (
          <p className="text-sm text-zinc-400">
            まだセッションがありません。
          </p>
        )}
      </div>

      {canStartNew && (
        <Button asChild>
          <Link href={`/sessions/new/${slug}`}>
            新しいセッションを始める
          </Link>
        </Button>
      )}
    </main>
  );
}
