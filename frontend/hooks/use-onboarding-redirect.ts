"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import type { User } from "@/types/api";

export function useOnboardingRedirect() {
  const router = useRouter();
  const { apiFetch } = useApi();
  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/auth/me/"),
  });

  useEffect(() => {
    if (user && !user.onboarding_done) {
      router.replace("/onboarding");
    }
  }, [user, router]);

  return user;
}
