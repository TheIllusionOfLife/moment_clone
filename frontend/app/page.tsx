import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { SignInButton, SignUpButton } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export default async function Home() {
  const { userId } = await auth();
  if (userId) redirect("/dashboard");

  return (
    <main className="flex flex-col items-center justify-center min-h-[calc(100vh-73px)] px-6 text-center">
      <h1 className="text-4xl font-bold text-zinc-900 mb-4">
        AIで料理が上手くなる
      </h1>
      <p className="text-lg text-zinc-500 mb-8 max-w-md">
        同じ料理を3回練習して、AIコーチからフィードバックをもらう。
        <br />
        料理の「原理原則」を体得しよう。
      </p>
      <div className="flex gap-3">
        <SignInButton mode="modal">
          <Button variant="outline">ログイン</Button>
        </SignInButton>
        <SignUpButton mode="modal">
          <Button>無料ではじめる</Button>
        </SignUpButton>
      </div>
    </main>
  );
}
