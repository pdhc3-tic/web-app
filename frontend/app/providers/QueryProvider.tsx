"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/**
 * Cliente do TanStack Query para toda a árvore protegida.
 *
 * `useState` guarda o `QueryClient` por instância do componente — sem isso, um
 * novo cliente seria criado a cada render, invalidando o cache. Não é um valor
 * derivado do resto do render: fica em estado exatamente para viver enquanto o
 * ProtectedLayout viver.
 *
 * Defaults escolhidos:
 * - `staleTime: 60_000` — as listagens das abas da ficha da UPF não mudam com
 *   frequência dentro de uma janela de 1 min; sem stale time as remontagens
 *   disparam refetch imediato e voltamos ao problema que a issue #271 pediu
 *   para eliminar.
 * - `refetchOnWindowFocus: false` — voltar do alt-tab não pode disparar N
 *   fetches simultâneos (Membros + Produção + Documentos + Histórico + resumo
 *   de composição familiar); o usuário aciona explicitamente via "Tentar
 *   novamente" quando quer.
 * - `retry: 1` — a mensagem de erro cobre os retries: `ApiError.message` já
 *   traz o texto do backend; três tentativas silenciosas atrasariam o feedback.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
