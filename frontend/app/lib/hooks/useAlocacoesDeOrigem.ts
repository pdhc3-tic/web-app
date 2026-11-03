import { useQuery } from "@tanstack/react-query";
import { getAtividade } from "@/app/lib/atividades";
import { fetchOrcamentoDaMeta } from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";

/**
 * Alocações que podem cobrir um remanejamento (#321, #363): as acima do
 * território, das rubricas pedidas, na Meta da atividade
 * (`GET /sgp/metas/{id}/orcamento/`). Hoje o detalhamento só traz as estaduais;
 * as nacionais dependem do backend (pendencias-backend-sprint-12.md, item 2).
 */
export function useAlocacoesDeOrigem(atividadeId: number | null, rubricas: string[]) {
  const atividade = useQuery({
    queryKey: qk.atividade(atividadeId ?? ""),
    queryFn: ({ signal }) => getAtividade(atividadeId!, signal),
    enabled: atividadeId !== null,
  });
  const metaId = atividade.data?.acao.meta?.id;

  const orcamento = useQuery({
    queryKey: qk.orcamentoDaMeta(metaId ?? 0),
    queryFn: ({ signal }) => fetchOrcamentoDaMeta(metaId!, signal),
    enabled: metaId !== undefined,
  });

  const alocacoes = (orcamento.data ?? [])
    .filter((r) => rubricas.includes(r.rubrica.slug))
    .flatMap((r) => r.detalhamento)
    .filter((a) => a.nivel !== "territorial");

  return { alocacoes, carregando: atividade.isPending || (metaId !== undefined && orcamento.isPending) };
}
