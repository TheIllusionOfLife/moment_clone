"use client";

import { useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useApi() {
  const { getToken } = useAuth();

  const apiFetch = useCallback(
    async function <T>(path: string, options?: RequestInit): Promise<T> {
      const token = await getToken();
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...options?.headers,
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(
          (body as { detail?: string }).detail ?? `HTTP ${res.status}`,
        );
      }
      return res.json() as Promise<T>;
    },
    [getToken],
  );

  const apiUpload = useCallback(
    async function <T>(path: string, body: FormData): Promise<T> {
      const token = await getToken();
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body,
      });
      if (!res.ok) {
        const resBody = await res.json().catch(() => ({}));
        throw new Error(
          (resBody as { detail?: string }).detail ?? `HTTP ${res.status}`,
        );
      }
      return res.json() as Promise<T>;
    },
    [getToken],
  );

  return { apiFetch, apiUpload };
}
