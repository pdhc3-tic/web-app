"use client";

import { useState } from "react";
import { logout } from "@/app/lib/api";
import Spinner from "@/app/components/ui/Spinner";

export function LogoutButton() {
  const [leaving, setLeaving] = useState(false);

  async function handleLogout() {
    setLeaving(true);
    await logout();
  }

  return (
    <button
      type="button"
      disabled={leaving}
      onClick={handleLogout}
      className="h-9 px-4 rounded-md border border-border bg-surface text-sm font-medium text-foreground hover:bg-surface-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2"
    >
      {leaving ? (
        <>
          <Spinner />
          <span>Saindo...</span>
        </>
      ) : (
        <span>Sair</span>
      )}
    </button>
  );
}
