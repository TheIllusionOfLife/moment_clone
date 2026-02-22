import type { ReactNode } from "react";
import { vi } from "vitest";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: async () => "test-token",
    isLoaded: true,
    isSignedIn: true,
  }),
  SignInButton: ({ children }: { children: ReactNode }) => children,
  SignUpButton: ({ children }: { children: ReactNode }) => children,
  SignedIn: ({ children }: { children: ReactNode }) => children,
  SignedOut: ({ children }: { children: ReactNode }) => children,
  UserButton: () => null,
  ClerkProvider: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@clerk/nextjs/server", () => ({
  auth: async () => ({
    userId: "test-user-id",
    sessionId: null,
    orgId: null,
    getToken: async () => "test-token",
    protect: async () => undefined,
    redirectToSignIn: async () => undefined,
  }),
}));
