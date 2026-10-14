"use client";

import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { perfisDecisoresSgd } from "@/app/lib/auth/roles";
import { fetchContagemFila, listDemandas } from "@/app/lib/demandas";
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
 * A fila "Aguardando minha ação" em si: a listagem filtrada pelos status que a
 * contagem informa para o perfil logado.
 */
export function useFilaDemandas() {
  const contagem = useContagemFila();
  const status = contagem.data?.status ?? [];

  const lista = useQuery({
    queryKey: qk.demandas.lista(status),
    queryFn: ({ signal }) => listDemandas({ status }, signal),
    enabled: contagem.decide && status.length > 0,
    staleTime: 30_000,
  });

  return {
    ...lista,
    // Sem status a aguardar (contagem carregada, fila vazia) não há o que listar.
    data: contagem.data && status.length === 0 ? [] : lista.data,
    isPending: contagem.isPending || (status.length > 0 && lista.isPending),
    error: contagem.error ?? lista.error,
    refetch: () => void Promise.all([contagem.refetch(), lista.refetch()]),
    decide: contagem.decide,
    total: contagem.data?.total,
  };
}
