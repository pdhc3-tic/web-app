import type { Acao } from "@/app/lib/acoes";
import type { PainelAcaoApi } from "@/app/lib/painel";
import type { AvaliacaoSemaforo } from "@/app/lib/semaforo";

/**
 * Meta como o painel precisa dela.
 *
 * O endpoint do painel devolve só `id`, `numero` e `titulo`; as datas vêm do
 * cruzamento com `/api/v1/metas/` e ficam nulas se a Meta não estiver naquela
 * listagem — daí serem opcionais aqui, e não `string` como em `MetaListItem`.
 */
export type MetaPainel = {
  id: number;
  numero: number;
  titulo: string;
  data_inicio: string | null;
  data_fim: string | null;
};

/**
 * Ação do painel pronta para a tela.
 *
 * `acao` é a fonte da verdade dos indicadores — vem do endpoint que calcula o
 * semáforo. `detalhe` é o cruzamento com `/api/v1/acoes/`, que traz os campos
 * descritivos ausentes na resposta do painel; é opcional de propósito, para que
 * a tela continue funcionando (só com menos texto) se esse cruzamento falhar.
 */
export type AcaoAvaliada = {
  acao: PainelAcaoApi;
  /** `null` quando a Ação não veio na listagem descritiva. */
  detalhe: Acao | null;
  meta: MetaPainel;
  avaliacao: AvaliacaoSemaforo;
};

/** Meta com suas Ações avaliadas — unidade dos cards-resumo. */
export type MetaComAcoes = {
  meta: MetaPainel;
  acoes: AcaoAvaliada[];
};
