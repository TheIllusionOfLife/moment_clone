import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CoachingChatPage from "@/app/chat/coaching/page";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("CoachingChatPage", () => {
  it("appends message optimistically after send", async () => {
    render(<CoachingChatPage />, { wrapper });

    await waitFor(() => {
      expect(
        screen.getByText("こんにちは！AIコーチです。"),
      ).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/質問や感想を入力/);
    fireEvent.change(textarea, {
      target: { value: "チャーハンのコツを教えて" },
    });

    const button = screen.getByRole("button", { name: "送信" });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);

    await waitFor(() => {
      expect(
        screen.getByText("チャーハンのコツを教えて"),
      ).toBeInTheDocument();
    });
  });

  it("shows AIコーチが返答中 after send", async () => {
    render(<CoachingChatPage />, { wrapper });

    await waitFor(() => screen.getByPlaceholderText(/質問や感想を入力/));

    const textarea = screen.getByPlaceholderText(/質問や感想を入力/);
    fireEvent.change(textarea, { target: { value: "テスト" } });

    const button = screen.getByRole("button", { name: "送信" });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/AIコーチが返答中/)).toBeInTheDocument();
    });
  });
});
