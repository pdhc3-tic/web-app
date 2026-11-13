import { useQueries } from "@tanstack/react-query";
import { fetchPoolsDaRubrica, type NivelOrcamento, type PoolOrcamentoApi } from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";

/** Os níveis acima do território: de onde o remanejamento pode tirar. */
const NIVEIS_DE_ORIGEM: NivelOrcamento[] = ["nacional", "estadual"];

/**
 * Pools que podem cobrir um remanejamento (#321, #363): os estaduais e o
 * nacional das rubricas pedidas, na matriz Rubrica × Nível
 * (`GET /sgp/orcamento/painel/?rubrica=&nivel=`, #384). Depois da #384 o saldo
 * não depende mais da Meta, então a atividade não entra na busca.
 *
 * O nacional vem primeiro, e os estaduais seguem em ordem de nome.
 */
export function usePoolsDeOrigem(rubricas: string[], habilitado = true) {
  const consultas = useQueries({
    queries: rubricas.flatMap((rubrica) =>
      NIVEIS_DE_ORIGEM.map((nivel) => ({
        queryKey: qk.poolsDaRubrica(rubrica, nivel),
        queryFn: ({ signal }: { signal: AbortSignal }) => fetchPoolsDaRubrica({ rubrica, nivel }, signal),
        enabled: habilitado,
        staleTime: 30_000,
      })),
    ),
  });

  const pools: PoolOrcamentoApi[] = consultas
    .flatMap((c) => c.data ?? [])
    .sort(
      (a, b) =>
        a.rubrica.nome.localeCompare(b.rubrica.nome, "pt-BR") ||
        (a.estado?.nome ?? "").localeCompare(b.estado?.nome ?? "", "pt-BR"),
    );

  return {
    pools,
    carregando: habilitado && consultas.some((c) => c.isPending),
    falhou: consultas.some((c) => c.isError),
  };
}
