import type { Rubrica } from "@/app/lib/tiposSolicitacao";
import { RUBRICA_SLUGS, type PoolOrcamentoApi } from "@/app/lib/orcamento";

/** Uma rubrica da dotação nacional, com o pool nacional dela, se já existe (#438). */
export type LinhaDotacao = {
  rubrica: Pick<Rubrica, "id" | "nome" | "slug" | "ativo">;
  /** O pool nacional da rubrica, ou null se a dotação ainda não foi lançada. */
  pool: PoolOrcamentoApi | null;
};

/**
 * As linhas da tela: as rubricas ativas, com ou sem pool, e as inativas que
 * ainda têm pool nacional (o valor delas continua existindo e pode ser
 * ajustado). Uma rubrica inativa sem pool fica de fora: lançar dotação nela
 * abriria orçamento para algo que o SGD não deixa mais pedir.
 *
 * A ordem é a de `RUBRICAS`, a mesma do Painel e da Distribuição; o que não
 * está nela vai para o fim, por nome.
 */
export function montarLinhas(rubricas: Rubrica[], poolsNacionais: PoolOrcamentoApi[]): LinhaDotacao[] {
  const poolPorRubrica = new Map<number, PoolOrcamentoApi>();
  for (const pool of poolsNacionais) {
    if (pool.nivel === "nacional") poolPorRubrica.set(pool.rubrica.id, pool);
  }

  const ordem = (slug: string) => {
    const i = RUBRICA_SLUGS.indexOf(slug);
    return i === -1 ? Number.MAX_SAFE_INTEGER : i;
  };

  return rubricas
    .filter((r) => r.ativo || poolPorRubrica.has(r.id))
    .map((r) => ({ rubrica: r, pool: poolPorRubrica.get(r.id) ?? null }))
    .sort(
      (a, b) =>
        ordem(a.rubrica.slug) - ordem(b.rubrica.slug) ||
        a.rubrica.nome.localeCompare(b.rubrica.nome, "pt-BR"),
    );
}
