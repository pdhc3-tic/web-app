import type { PainelAcaoApi } from "@/app/lib/painel";

/**
 * Semáforo de execução das Ações do Plano de Trabalho (RF17).
 *
 * ─── Quem classifica ────────────────────────────────────────────────────────
 *
 * O BACKEND. A regra vive em `apps/sgp/services/workplan_dashboard.py`:
 * verde quando o realizado alcança o esperado, amarelo a partir de metade do
 * esperado, vermelho abaixo disso. Este módulo só rotula, agrega e formata o
 * que vem de lá. Classificar de novo aqui criaria uma segunda verdade, e o
 * alerta diário por e-mail (apps/sgp/tasks.py) usa a do backend.
 *
 * ─── De onde sai o "esperado" ───────────────────────────────────────────────
 *
 * Não há curva de execução planejada no domínio: WorkPlanAcao guarda apenas
 * `quantidade_planejada` e deriva `quantidade_realizada`. O esperado é, então,
 * o TEMPO DECORRIDO do período da Ação — metade do prazo passou, espera-se
 * metade da entrega. É uma reta, e execução real não é uniforme (obras
 * concentram entrega no fim, capacitações no começo). É a única leitura
 * possível com os dados existentes, e por isso a tela nomeia o critério em vez
 * de exibir um número mágico.
 *
 * Vale lembrar o viés que vem de baixo, já documentado em acoes.ts: o realizado
 * é CONTAGEM de Atividades concluídas, não soma de unidades entregues. Para
 * Ações medidas em quantidade ("família atendida") o semáforo pesa para o
 * vermelho — o problema é do dado de origem, não da regra daqui.
 */

// ─── Níveis ─────────────────────────────────────────────────────────────────

/** Os três do backend, mais o `sem-dado` que a UI acrescenta (ver nivelDaApi). */
export type NivelSemaforo = "verde" | "amarelo" | "vermelho" | "sem-dado";

/**
 * Razão realizado/esperado abaixo da qual a Ação está vermelha e entra no
 * alerta. 0,5 é o critério da issue — "progresso abaixo de 50% do esperado" — e
 * o mesmo multiplicador de `_semaphore` no backend. Aqui serve só para escrever
 * o número no texto do alerta, não para classificar.
 */
export const LIMIAR_VERMELHO = 0.5;

/** Níveis do semáforo propriamente dito, na ordem em que a UI os apresenta. */
export const NIVEIS_SEMAFORO = ["verde", "amarelo", "vermelho"] as const;

const NIVEL_LABEL: Record<NivelSemaforo, string> = {
  verde: "No ritmo",
  amarelo: "Atenção",
  vermelho: "Crítica",
  "sem-dado": "Sem dado",
};

export function nivelLabel(nivel: NivelSemaforo): string {
  return NIVEL_LABEL[nivel];
}

// ─── Tradução da resposta do painel ─────────────────────────────────────────

/** Período de referência; a Meta serve de fallback para Ações sem datas. */
export type Periodo = {
  data_inicio: string | null;
  data_fim: string | null;
};

export type AvaliacaoSemaforo = {
  nivel: NivelSemaforo;
  /** 0–100. `null` quando não há quantidade planejada para comparar. */
  realizado: number | null;
  /** 0–100. `null` quando não há período conhecido. */
  esperado: number | null;
  /** Datas efetivamente usadas — a UI mostra quando vieram da Meta. */
  periodo: Periodo;
  /** true quando a Ação não tem datas próprias e herdou as da Meta. */
  periodoHerdado: boolean;
};

/**
 * Nível exibido para uma Ação do painel.
 *
 * É o `semaforo` do backend, com uma única ressalva: sem quantidade planejada
 * não há denominador, e o backend classifica esse caso como vermelho porque
 * 0/0 vira 0%. Deixar passar colocaria um alarme falso justamente na seção mais
 * visível da tela, então a UI o exibe como "Sem dado" — dizer que não se sabe é
 * mais honesto que dizer que está crítico.
 */
export function nivelDaApi(acao: PainelAcaoApi): NivelSemaforo {
  if (Number(acao.quantidade_planejada) <= 0) return "sem-dado";
  return acao.semaforo;
}

/** Decimal do DRF ("53.60") → number, ou `null` quando não há o que exibir. */
function percentual(valor: string | null, temDenominador: boolean): number | null {
  if (!temDenominador) return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

/**
 * Converte uma Ação do painel na forma que os componentes consomem.
 *
 * O backend calcula `progresso_esperado` já herdando as datas da Meta, mas
 * devolve `data_inicio`/`data_fim` crus. A herança é refeita aqui só para
 * rotular o período — nenhum indicador é recalculado.
 */
export function avaliacaoDaApi(
  acao: PainelAcaoApi,
  meta: Periodo | null = null,
): AvaliacaoSemaforo {
  const temDatasProprias = Boolean(acao.data_inicio && acao.data_fim);
  const herdado = !temDatasProprias && Boolean(meta?.data_inicio && meta?.data_fim);

  const periodo: Periodo = herdado
    ? { data_inicio: meta!.data_inicio, data_fim: meta!.data_fim }
    : { data_inicio: acao.data_inicio, data_fim: acao.data_fim };

  const temDenominador = Number(acao.quantidade_planejada) > 0;
  const temPeriodo = Boolean(periodo.data_inicio && periodo.data_fim);

  return {
    nivel: nivelDaApi(acao),
    realizado: percentual(acao.percentual_realizado, temDenominador),
    esperado: percentual(acao.progresso_esperado, temPeriodo),
    periodo,
    periodoHerdado: herdado,
  };
}

// ─── Agregação ──────────────────────────────────────────────────────────────

export type ContagemSemaforo = Record<NivelSemaforo, number>;

export function contagemVazia(): ContagemSemaforo {
  return { verde: 0, amarelo: 0, vermelho: 0, "sem-dado": 0 };
}

export function contarNiveis(
  avaliacoes: ReadonlyArray<{ nivel: NivelSemaforo }>,
): ContagemSemaforo {
  const total = contagemVazia();
  for (const a of avaliacoes) total[a.nivel] += 1;
  return total;
}

/** "53,6%" — percentual em pt-BR com uma casa. Traço quando não há valor. */
export function formatPercentual(valor: number | null): string {
  if (valor === null) return "—";
  return `${valor.toFixed(1).replace(".", ",")}%`;
}
