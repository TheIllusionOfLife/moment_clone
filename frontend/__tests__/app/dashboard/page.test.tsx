import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "@/app/dashboard/page";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

vi.mock("@/hooks/use-onboarding-redirect", () => ({
  useOnboardingRedirect: () => ({ onboarding_done: true }),
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

describe("DashboardPage", () => {
  it("renders 3 dish cards", async () => {
    render(<DashboardPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("チャーハン")).toBeInTheDocument();
      expect(screen.getByText("ビーフステーキ")).toBeInTheDocument();
      expect(screen.getByText("ポモドーロ")).toBeInTheDocument();
    });
  });

  it("shows はじめる for not_started dish", async () => {
    render(<DashboardPage />, { wrapper });
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: "はじめる" }),
      ).toBeInTheDocument();
    });
  });

  it("shows 完了 badge for completed dish", async () => {
    render(<DashboardPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("完了")).toBeInTheDocument();
    });
  });
});
