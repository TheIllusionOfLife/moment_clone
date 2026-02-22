import Link from "next/link";
import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export function AppHeader() {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
      <Link href="/" className="font-semibold text-zinc-900">
        moment
      </Link>
      <div className="flex items-center gap-3">
        <SignedOut>
          <SignInButton>
            <Button variant="ghost" size="sm">
              ログイン
            </Button>
          </SignInButton>
          <SignUpButton>
            <Button size="sm">はじめる</Button>
          </SignUpButton>
        </SignedOut>
        <SignedIn>
          <UserButton />
        </SignedIn>
      </div>
    </header>
  );
}
