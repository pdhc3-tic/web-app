"use client";

import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { perfisDecisoresSgd } from "@/app/lib/auth/roles";
import { listDemandas, STATUS_AGUARDANDO, type StatusDemanda } from "@/app/lib/demandas";
import { qk } from "@/app/lib/queryKeys";

/**
 * Fila "Aguardando minha ação" do SGD (#296): as demandas nos status que cabem
 * ao(s) perfil(is) do usuário decidir. A mesma consulta alimenta a aba do
 * painel e o badge "N pendentes" da sidebar — uma requisição, um cache.
 *
 * Quem não decide (ADT, Super Admin sem outro perfil) não tem fila.
 */
export function useFilaDemandas() {
  const { data: session } = useSession();
  const perfis = perfisDecisoresSgd(session?.user);
  const status: StatusDemanda[] = [...new Set(perfis.flatMap((p) => STATUS_AGUARDANDO[p]))];

  const query = useQuery({
    queryKey: qk.demandas.lista(status),
    queryFn: ({ signal }) => listDemandas({ status }, signal),
    enabled: status.length > 0,
    staleTime: 30_000,
  });

  return { ...query, decide: status.length > 0, status };
}
