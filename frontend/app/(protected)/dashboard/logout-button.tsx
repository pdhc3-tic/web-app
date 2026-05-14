"use client";

import { useTransition } from "react";
import { logout } from "@/app/lib/api";

export function LogoutButton() {
  const [pending, startTransition] = useTransition();

  return (
    <button
      type="button"
      disabled={pending}
      onClick={() => startTransition(() => logout())}
      className="h-9 px-4 rounded-md border border-border bg-surface text-sm font-medium text-foreground hover:bg-surface-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {pending ? "Saindo..." : "Sair"}
    </button>
  );
}
