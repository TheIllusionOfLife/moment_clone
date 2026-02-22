import type { ReactNode } from "react";
import { vi } from "vitest";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
  SignInButton: ({ children }: { children: ReactNode }) => children,
  SignUpButton: ({ children }: { children: ReactNode }) => children,
  SignedIn: ({ children }: { children: ReactNode }) => children,
  SignedOut: ({ children }: { children: ReactNode }) => children,
  UserButton: () => null,
  ClerkProvider: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@clerk/nextjs/server", () => ({
  auth: async () => ({ userId: "test-user-id" }),
}));
