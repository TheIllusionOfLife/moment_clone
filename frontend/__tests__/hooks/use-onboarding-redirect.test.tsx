import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useOnboardingRedirect } from "../../hooks/use-onboarding-redirect";
import { server } from "../mocks/server";
import { http, HttpResponse } from "msw";

// Mock next/navigation
const mockRouter = {
  replace: vi.fn(),
  push: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

// Mock @clerk/nextjs
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: async () => "test-token",
    isLoaded: true,
    isSignedIn: true,
  }),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe("useOnboardingRedirect", () => {
  beforeEach(() => {
    queryClient.clear();
    mockRouter.replace.mockClear();
    server.resetHandlers();
  });

  it("should redirect to /onboarding if user is not onboarded", async () => {
    server.use(
      http.get("*/api/auth/me/", () => {
        return HttpResponse.json({
          id: 1,
          clerk_user_id: "user_test",
          email: "test@example.com",
          first_name: "Test",
          onboarding_done: false, // Not onboarded
          subscription_status: "free",
          learner_profile: null,
          created_at: "2024-01-01T00:00:00Z",
        });
      })
    );

    const { result } = renderHook(() => useOnboardingRedirect(), { wrapper });

    await waitFor(() => {
      expect(result.current).toBeDefined();
    });

    expect(mockRouter.replace).toHaveBeenCalledWith("/onboarding");
  });

  it("should NOT redirect if user is already onboarded", async () => {
    server.use(
      http.get("*/api/auth/me/", () => {
        return HttpResponse.json({
          id: 1,
          clerk_user_id: "user_test",
          email: "test@example.com",
          first_name: "Test",
          onboarding_done: true, // Onboarded
          subscription_status: "free",
          learner_profile: null,
          created_at: "2024-01-01T00:00:00Z",
        });
      })
    );

    const { result } = renderHook(() => useOnboardingRedirect(), { wrapper });

    await waitFor(() => {
      expect(result.current).toBeDefined();
    });

    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  it("should NOT redirect if API returns an error", async () => {
    server.use(
      http.get("*/api/auth/me/", () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    const { result } = renderHook(() => useOnboardingRedirect(), { wrapper });

    await waitFor(() => {
      expect(queryClient.getQueryState(["me"])?.status).toBe("error");
    });

    expect(mockRouter.replace).not.toHaveBeenCalled();
  });
});
