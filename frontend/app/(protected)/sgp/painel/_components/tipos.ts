import type { Acao } from "@/app/lib/acoes";
import type { MetaListItem } from "@/app/lib/metas";
import type { AvaliacaoSemaforo } from "@/app/lib/semaforo";

/** Ação já classificada no semáforo, com a Meta a que pertence. */
export type AcaoAvaliada = {
  acao: Acao;
  /** `null` quando a Ação aponta para uma Meta fora da listagem carregada. */
  meta: MetaListItem | null;
  avaliacao: AvaliacaoSemaforo;
};

/** Meta com suas Ações avaliadas — unidade dos cards-resumo. */
export type MetaComAcoes = {
  meta: MetaListItem;
  acoes: AcaoAvaliada[];
};
