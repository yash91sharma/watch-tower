// The frame of the pages before the login (setup and login): the logo and the product
// name, and a card with the page title and the form, in the center of the window.
import type { ReactNode } from "react";

import { Logo } from "@/components/Logo";

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 px-4 py-8">
      <div className="flex flex-col items-center gap-2">
        <Logo className="size-12" />
        <p className="text-lg font-semibold">Watch Tower</p>
      </div>
      <div className="w-full max-w-md space-y-4 rounded-xl border bg-card p-6 shadow-xs">
        <h1 className="text-xl font-semibold">{title}</h1>
        {children}
      </div>
    </main>
  );
}
