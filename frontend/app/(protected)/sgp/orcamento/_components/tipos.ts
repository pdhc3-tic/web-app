import type { PoolOrcamentoApi, RubricaApi } from "@/app/lib/orcamento";
import type { NivelSemaforo } from "@/app/lib/semaforo";

/**
 * Um pool da matriz pronto para a tela (#398).
 *
 * `linha` é a fonte da verdade — vem do endpoint que calcula o semáforo. Os
 * demais campos são derivações dela, calculadas uma vez na montagem para que a
 * tabela, o banner de alerta e o SlideOver leiam sempre o mesmo valor.
 */
export type CelulaOrcamento = {
  linha: PoolOrcamentoApi;
  /** Semáforo do backend, com "sem-dado" quando não há valor aprovado. */
  nivelSemaforo: NivelSemaforo;
  /** Comprometido sobre aprovado, 0–100. `null` sem denominador. */
  percentual: number | null;
  /** true quando nenhum dos quatro valores lançados é diferente de zero. */
  vazia: boolean;
  /** Recuo na árvore: 0 nacional, 1 estado, 2 território (1 se o estado dele não está no recorte). */
  profundidade: 0 | 1 | 2;
};

/** Uma rubrica com os seus pools em árvore: a unidade de agrupamento da matriz Rubrica × Nível. */
export type RubricaComPools = {
  rubrica: RubricaApi;
  celulas: CelulaOrcamento[];
};
