import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "@/__tests__/mocks/server";
import SessionDetailPage from "@/app/sessions/[id]/page";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("SessionDetailPage", () => {
  it("shows spinner when processing", async () => {
    server.use(
      http.get("http://localhost:8000/api/sessions/1/", () =>
        HttpResponse.json({
          id: 1,
          status: "processing",
          coaching_text: null,
          coaching_video_url: null,
          pipeline_error: null,
          session_number: 1,
        }),
      ),
    );
    render(<SessionDetailPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/AI分析中/)).toBeInTheDocument();
    });
  });

  it("shows coaching text when text_ready", async () => {
    server.use(
      http.get("http://localhost:8000/api/sessions/1/", () =>
        HttpResponse.json({
          id: 1,
          status: "text_ready",
          session_number: 1,
          coaching_text: {
            mondaiten: "火加減が弱い",
            skill: "中火をマスター",
            next_action: "次は中火で",
            success_sign: "きつね色になる",
          },
          coaching_video_url: null,
          pipeline_error: null,
        }),
      ),
    );
    render(<SessionDetailPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("火加減が弱い")).toBeInTheDocument();
    });
  });

  it("shows video when completed", async () => {
    server.use(
      http.get("http://localhost:8000/api/sessions/1/", () =>
        HttpResponse.json({
          id: 1,
          status: "completed",
          session_number: 1,
          coaching_text: {
            mondaiten: "ok",
            skill: "ok",
            next_action: "ok",
            success_sign: "ok",
          },
          coaching_video_url: "https://example.com/video.mp4",
          pipeline_error: null,
        }),
      ),
    );
    render(<SessionDetailPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/コーチング動画/)).toBeInTheDocument();
    });
  });
});
