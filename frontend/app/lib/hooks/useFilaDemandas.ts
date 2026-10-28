"use client";

import { useSession } from "next-auth/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { perfisDecisoresSgd } from "@/app/lib/auth/roles";
import { fetchContagemFila, listDemandas, type PaginaDemandas } from "@/app/lib/demandas";
import { qk } from "@/app/lib/queryKeys";

/**
 * Contagem da fila "Aguardando minha ação" do SGD (#296) — a do badge da
 * sidebar e do card do `/sgd`. Vem pronta do backend
 * (`aguardando-minha-acao/contagem`), com a regra de cada perfil aplicada lá.
 *
 * Quem não decide (ADT, Super Admin sem outro perfil) não consulta: não há fila.
 */
export function useContagemFila() {
  const { data: session } = useSession();
  const decide = perfisDecisoresSgd(session?.user).length > 0;

  const query = useQuery({
    queryKey: qk.demandas.contagemFila,
    queryFn: ({ signal }) => fetchContagemFila(signal),
    enabled: decide,
    staleTime: 30_000,
  });

  return { ...query, decide };
}

/**
 * A fila "Aguardando minha ação" em si: a listagem com
 * `?aguardando_minha_acao=true`, pela mesma regra da contagem, uma página por
 * vez (#323). A página anterior fica na tela enquanto a próxima carrega.
 */
export function useFilaDemandas(pagina: PaginaDemandas) {
  const contagem = useContagemFila();

  const lista = useQuery({
    queryKey: qk.demandas.filaPagina(pagina),
    queryFn: ({ signal }) => listDemandas({ aguardandoMinhaAcao: true, pagina }, signal),
    enabled: contagem.decide,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  return {
    ...lista,
    error: contagem.error ?? lista.error,
    refetch: () => void Promise.all([contagem.refetch(), lista.refetch()]),
    decide: contagem.decide,
    total: contagem.data?.total,
  };
}
