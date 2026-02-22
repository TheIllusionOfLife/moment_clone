"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

const QUESTIONS = [
  {
    id: "skill_level",
    question: "現在の料理スキルは？",
    options: [
      { value: "beginner", label: "初心者（レシピなしでは作れない）" },
      { value: "intermediate", label: "中級者（基本的な料理はできる）" },
      { value: "advanced", label: "上級者（様々な料理を自在に作れる）" },
    ],
  },
  {
    id: "frequency",
    question: "週に何回料理しますか？",
    options: [
      { value: "rarely", label: "ほとんどしない" },
      { value: "sometimes", label: "週1〜2回" },
      { value: "often", label: "週3〜5回" },
      { value: "daily", label: "毎日" },
    ],
  },
  {
    id: "weak_area",
    question: "最も苦手な料理の工程は？",
    options: [
      { value: "heat", label: "火加減のコントロール" },
      { value: "timing", label: "複数の工程の段取り" },
      { value: "seasoning", label: "味付け・調味料のバランス" },
      { value: "technique", label: "切り方・下ごしらえ" },
    ],
  },
  {
    id: "goal",
    question: "料理を上達させたい目的は？",
    options: [
      { value: "daily", label: "日々の食事を豊かにしたい" },
      { value: "impress", label: "家族・友人に喜ばれる料理を作りたい" },
      { value: "health", label: "健康的な食生活を維持したい" },
      { value: "enjoy", label: "料理自体を楽しみたい" },
    ],
  },
  {
    id: "learning_style",
    question: "学習スタイルは？",
    options: [
      { value: "theory", label: "理論から理解したい" },
      { value: "practice", label: "まず実践してみたい" },
      { value: "feedback", label: "フィードバックを受けながら改善したい" },
    ],
  },
  {
    id: "commitment",
    question: "練習に使える時間は？",
    options: [
      { value: "low", label: "週1回程度" },
      { value: "medium", label: "週2〜3回" },
      { value: "high", label: "毎日でも" },
    ],
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { apiFetch } = useApi();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const allAnswered = QUESTIONS.every((q) => answers[q.id]);

  async function handleSubmit() {
    if (!allAnswered) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await apiFetch("/api/auth/me/", {
        method: "PATCH",
        body: JSON.stringify({ learner_profile: { answers } }),
      });
      router.replace("/dashboard");
    } catch (e) {
      setSubmitError(
        e instanceof Error ? e.message : "保存に失敗しました。もう一度お試しください。",
      );
      setSubmitting(false);
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-zinc-900 mb-2">
        あなたについて教えてください
      </h1>
      <p className="text-zinc-500 mb-8">
        AIコーチがあなた専用のコーチングプランを作成します。
      </p>

      <div className="space-y-6">
        {QUESTIONS.map((q) => (
          <Card key={q.id}>
            <CardHeader>
              <CardTitle className="text-base">{q.question}</CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup
                value={answers[q.id] ?? ""}
                onValueChange={(v) =>
                  setAnswers((prev) => ({ ...prev, [q.id]: v }))
                }
                className="space-y-2"
              >
                {q.options.map((opt) => (
                  <div key={opt.value} className="flex items-center gap-2">
                    <RadioGroupItem
                      value={opt.value}
                      id={`${q.id}-${opt.value}`}
                    />
                    <Label htmlFor={`${q.id}-${opt.value}`}>
                      {opt.label}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>
        ))}
      </div>

      {submitError && (
        <p className="mt-4 text-sm text-red-600">{submitError}</p>
      )}
      <Button
        className="mt-4 w-full"
        disabled={!allAnswered || submitting}
        onClick={handleSubmit}
      >
        {submitting ? "保存中..." : "はじめる →"}
      </Button>
    </main>
  );
}
