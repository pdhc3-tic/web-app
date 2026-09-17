import type {
  MetaOrcamentoApi,
  NivelOrcamento,
  PainelOrcamentoLinhaApi,
} from "@/app/lib/orcamento";
import type { NivelSemaforo } from "@/app/lib/semaforo";

/**
 * Uma célula da matriz pronta para a tela.
 *
 * `linha` é a fonte da verdade — vem do endpoint que calcula o semáforo. Os
 * outros três campos são derivações puras dela (ver `lib/orcamento.ts`),
 * calculadas uma vez na montagem para que a tabela, o banner de alerta e o
 * SlideOver leiam sempre o mesmo valor em vez de recalcular cada um por si.
 */
export type CelulaOrcamento = {
  linha: PainelOrcamentoLinhaApi;
  /** Semáforo do backend, com "sem-dado" quando não há valor aprovado. */
  nivelSemaforo: NivelSemaforo;
  /** Comprometido sobre aprovado, 0–100. `null` sem denominador. */
  percentual: number | null;
  /** true quando nenhum dos quatro valores lançados é diferente de zero. */
  vazia: boolean;
};

/** Uma Meta com as suas rubricas — a unidade de agrupamento da matriz. */
export type MetaComRubricas = {
  meta: MetaOrcamentoApi;
  celulas: CelulaOrcamento[];
};

/**
 * O escopo que o backend resolveu para esta resposta.
 *
 * O nível não é escolhido pela tela: `resolver_nivel_painel` o deriva do perfil
 * do usuário e dos filtros de drill-down. A tela lê o `nivel` que voltou nas
 * linhas para poder NOMEAR o que está mostrando — sem isso, "aprovado" seria
 * lido como um recorte dos mesmos números quando na verdade é outro nível da
 * hierarquia.
 */
export type EscopoExibido = {
  nivel: NivelOrcamento;
  /** Nome do estado ou território, quando conhecido. */
  nomeLocal: string | null;
};
