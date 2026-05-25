"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { logout } from "@/app/lib/api";
import Spinner from "@/app/components/ui/Spinner";
import { PAGE_HEADER_SLOT_ID } from "./PageHeader";

function getIniciais(nome: string): string {
  const partes = nome.split(" ").filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0][0]?.toUpperCase() ?? "?";
  return (
    (partes[0][0] ?? "") + (partes[partes.length - 1][0] ?? "")
  ).toUpperCase();
}

function UserMenu() {
  const { data: session } = useSession();
  const [leaving, setLeaving] = useState(false);

  async function handleLogout() {
    setLeaving(true);
    await logout();
  }

  if (!session?.user) return null;

  const { nome_completo, foto_url } = session.user;
  const nome = nome_completo || "Usuário";
  const iniciais = getIniciais(nome);

  return (
    <div className="flex items-center gap-3">
      {foto_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={foto_url}
          alt=""
          className="h-8 w-8 rounded-full object-cover border border-border shrink-0"
        />
      ) : (
        <div
          aria-hidden="true"
          className="h-8 w-8 rounded-full bg-primary text-surface text-xs font-medium flex items-center justify-center shrink-0"
        >
          {iniciais}
        </div>
      )}
      <span className="hidden sm:block text-sm font-medium text-text truncate max-w-[180px]">
        {nome}
      </span>
      <button
        type="button"
        disabled={leaving}
        onClick={handleLogout}
        className="h-9 px-3 rounded-md border border-border bg-surface text-sm font-medium text-text hover:bg-surface-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2"
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
    </div>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-20 h-14 bg-surface border-b border-border flex items-center justify-between gap-4 px-6">
      <div id={PAGE_HEADER_SLOT_ID} className="flex-1 min-w-0" />
      <UserMenu />
    </header>
  );
}
