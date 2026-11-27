"use client";

import { useEffect } from "react";
import type { Session } from "next-auth";
import { SessionProvider as NextAuthSessionProvider, useSession } from "next-auth/react";
import { guardarSessao } from "@/app/lib/auth/tokenCache";

/** Mantém o token do `apiClient` igual ao da sessão quando ela muda (foco da aba, renovação). */
function SincronizarToken() {
  const { data } = useSession();
  useEffect(() => {
    guardarSessao(data);
  }, [data]);
  return null;
}

/**
 * Sessão da área logada (#448). O layout já leu a sessão no servidor e a
 * passa aqui: a `useSession()` começa preenchida, sem buscar
 * `/api/auth/session` ao montar, e o menu não muda de forma enquanto ela
 * chegaria. O token vai direto para o cache do `apiClient`, já no render, para
 * as primeiras consultas não precisarem relê-la.
 */
export default function SessionProvider({
  session,
  children,
}: {
  session: Session | null;
  children: React.ReactNode;
}) {
  guardarSessao(session);
  return (
    <NextAuthSessionProvider session={session}>
      <SincronizarToken />
      {children}
    </NextAuthSessionProvider>
  );
}
