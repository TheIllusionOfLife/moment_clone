import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useApi } from "@/lib/api";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

describe("useApi", () => {
  it("injects Bearer token into requests", async () => {
    let capturedHeaders: HeadersInit | undefined;
    const originalFetch = global.fetch;
    global.fetch = vi.fn(async (_url, init) => {
      capturedHeaders = init?.headers;
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    const { result } = renderHook(() => useApi());
    await result.current.apiFetch("/test");

    expect(capturedHeaders).toMatchObject({
      Authorization: "Bearer test-token",
    });
    global.fetch = originalFetch;
  });

  it("throws on non-ok response", async () => {
    const originalFetch = global.fetch;
    global.fetch = vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
    );

    const { result } = renderHook(() => useApi());
    await expect(result.current.apiFetch("/missing")).rejects.toThrow(
      "Not found",
    );
    global.fetch = originalFetch;
  });

  it("apiUpload omits Content-Type header", async () => {
    let capturedHeaders: Record<string, string> | undefined;
    const originalFetch = global.fetch;
    global.fetch = vi.fn(async (_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    const { result } = renderHook(() => useApi());
    const fd = new FormData();
    await result.current.apiUpload("/upload", fd);

    expect(capturedHeaders?.["Content-Type"]).toBeUndefined();
    global.fetch = originalFetch;
  });
});
