"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import { useOnboardingRedirect } from "@/hooks/use-onboarding-redirect";
import type { Dish } from "@/types/api";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const DISH_VISUALS: Record<string, { emoji: string; bg: string }> = {
  "fried-rice": { emoji: "🍳", bg: "bg-amber-50" },
  "beef-steak": { emoji: "🥩", bg: "bg-red-50" },
  pomodoro: { emoji: "🍅", bg: "bg-orange-50" },
};

function DishImage({ slug }: { slug: string }) {
  const visual = DISH_VISUALS[slug] ?? { emoji: "🍽️", bg: "bg-zinc-50" };
  return (
    <div
      className={`${visual.bg} flex items-center justify-center h-32 text-5xl rounded-t-lg`}
    >
      {visual.emoji}
    </div>
  );
}

function ProgressDots({ status }: { status: string }) {
  const filled =
    status === "completed" ? 3 : status === "in_progress" ? 1 : 0;
  return (
    <div className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`w-2 h-2 rounded-full ${i < filled ? "bg-zinc-900" : "bg-zinc-200"}`}
        />
      ))}
    </div>
  );
}

export default function DashboardPage() {
  useOnboardingRedirect();
  const { apiFetch } = useApi();
  const { data: dishes, isLoading, isError } = useQuery<Dish[]>({
    queryKey: ["dishes"],
    queryFn: () => apiFetch<Dish[]>("/api/dishes/"),
  });

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-zinc-900 mb-2">
        練習する料理を選ぶ
      </h1>
      <p className="text-zinc-500 mb-8">
        同じ料理を3回練習して、AIコーチからフィードバックをもらいましょう。
      </p>

      {isError ? (
        <p className="text-sm text-red-600">料理の読み込みに失敗しました。</p>
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          {dishes?.map((dish) => (
            <Card key={dish.id} className="flex flex-col overflow-hidden">
              <DishImage slug={dish.slug} />
              <CardHeader>
                <CardTitle className="text-lg">{dish.name_ja}</CardTitle>
                <p className="text-sm text-zinc-500">{dish.name_en}</p>
              </CardHeader>
              <CardContent className="flex-1">
                <p className="text-sm text-zinc-600">
                  {dish.description_ja}
                </p>
                <div className="mt-3">
                  <ProgressDots status={dish.progress.status} />
                </div>
              </CardContent>
              <CardFooter>
                {dish.progress.status === "completed" ? (
                  <Badge
                    variant="secondary"
                    className="w-full justify-center py-1"
                  >
                    完了
                  </Badge>
                ) : (
                  <Button asChild className="w-full" size="sm">
                    <Link href={`/dishes/${dish.slug}`}>
                      {dish.progress.status === "not_started"
                        ? "はじめる"
                        : "続ける"}
                    </Link>
                  </Button>
                )}
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
