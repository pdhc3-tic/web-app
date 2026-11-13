import {
  linhaVazia,
  nivelDaLinha,
  percentualComprometido,
  type PoolOrcamentoApi,
} from "@/app/lib/orcamento";
import type { CelulaOrcamento, RubricaComPools } from "./tipos";

function celula(linha: PoolOrcamentoApi, profundidade: CelulaOrcamento["profundidade"]): CelulaOrcamento {
  return {
    linha,
    nivelSemaforo: nivelDaLinha(linha),
    percentual: percentualComprometido(linha),
    vazia: linhaVazia(linha),
    profundidade,
  };
}

const porNome = (a: string, b: string) => a.localeCompare(b, "pt-BR");

/**
 * A lista plana do painel → a matriz Rubrica × Nível em árvore (#398).
 *
 * O backend ordena por rubrica e nível (todos os estaduais, depois todos os
 * territoriais). A tela quer ler de cima para baixo como o dinheiro desce:
 * Nacional → cada estado → os territórios desse estado. Um território entra
 * sob o primeiro estado dele que está no recorte; sem nenhum (o ADT, ou o
 * filtro por território), fica no nível de cima. Nada é recalculado aqui.
 */
export function montarMatriz(pools: readonly PoolOrcamentoApi[]): RubricaComPools[] {
  const porRubrica = new Map<number, { rubrica: PoolOrcamentoApi["rubrica"]; pools: PoolOrcamentoApi[] }>();
  for (const pool of pools) {
    const grupo = porRubrica.get(pool.rubrica.id) ?? { rubrica: pool.rubrica, pools: [] };
    grupo.pools.push(pool);
    porRubrica.set(pool.rubrica.id, grupo);
  }

  return [...porRubrica.values()].map(({ rubrica, pools: daRubrica }) => {
    const nacionais = daRubrica.filter((p) => p.nivel === "nacional");
    const estaduais = daRubrica
      .filter((p) => p.nivel === "estadual")
      .sort((a, b) => porNome(a.estado?.nome ?? "", b.estado?.nome ?? ""));
    const territoriais = daRubrica
      .filter((p) => p.nivel === "territorial")
      .sort((a, b) => porNome(a.territorio?.nome ?? "", b.territorio?.nome ?? ""));

    const siglas = new Set(estaduais.map((e) => e.estado?.sigla));
    const estadoDoTerritorio = (p: PoolOrcamentoApi) => p.territorio?.estados?.find((s) => siglas.has(s));
    const temRaiz = nacionais.length > 0;

    const celulas: CelulaOrcamento[] = nacionais.map((p) => celula(p, 0));
    for (const estadual of estaduais) {
      celulas.push(celula(estadual, temRaiz ? 1 : 0));
      for (const territorial of territoriais) {
        if (estadoDoTerritorio(territorial) === estadual.estado?.sigla) {
          celulas.push(celula(territorial, temRaiz ? 2 : 1));
        }
      }
    }
    for (const territorial of territoriais) {
      if (!estadoDoTerritorio(territorial)) celulas.push(celula(territorial, temRaiz ? 1 : 0));
    }
    return { rubrica, celulas };
  });
}
