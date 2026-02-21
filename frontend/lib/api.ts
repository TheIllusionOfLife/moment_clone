"use client";

import { useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? `HTTP ${res.status}`,
    );
  }
  return res.json() as Promise<T>;
}

export function useApi() {
  const { getToken } = useAuth();

  const apiFetch = useCallback(
    async function <T>(path: string, options?: RequestInit): Promise<T> {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...options?.headers,
        },
      });
      return handleResponse<T>(res);
    },
    [getToken],
  );

  const apiUpload = useCallback(
    async function <T>(path: string, body: FormData): Promise<T> {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body,
      });
      return handleResponse<T>(res);
    },
    [getToken],
  );

  return { apiFetch, apiUpload };
}
