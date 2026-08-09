import { progressoAcao, type Acao } from "@/app/lib/acoes";
import { parseDateOnly } from "@/app/lib/datetime";

/**
 * Semáforo de execução das Ações do Plano de Trabalho (RF17).
 *
 * ─── De onde sai o "esperado" ───────────────────────────────────────────────
 *
 * O backend NÃO tem curva de execução planejada: WorkPlanAcao guarda apenas
 * `quantidade_planejada`, deriva `quantidade_realizada` (contagem de Atividades
 * concluídas) e um `status_execucao` binário por data de fim. Não existe campo
 * dizendo quanto já deveria ter sido entregue nesta altura do projeto.
 *
 * O esperado aqui é, então, o TEMPO DECORRIDO do período da Ação: metade do
 * prazo passou → espera-se metade da entrega. É uma reta, e execução real não é
 * uniforme (obras concentram entrega no fim, capacitações no começo). É a única
 * leitura possível com os dados existentes, e por isso a tela nomeia o critério
 * em vez de exibir um número mágico.
 *
 * Vale lembrar o viés que vem de baixo, já documentado em acoes.ts: o realizado
 * é CONTAGEM de Atividades concluídas, não soma de unidades entregues. Para
 * Ações medidas em quantidade ("família atendida") o semáforo pesa para o
 * vermelho — o problema é do dado de origem, não da regra daqui.
 */

// ─── Níveis e limiares ──────────────────────────────────────────────────────

export type NivelSemaforo = "verde" | "amarelo" | "vermelho" | "sem-dado";

/** A partir desta razão realizado/esperado a Ação está verde. */
export const LIMIAR_VERDE = 0.9;

/**
 * Abaixo desta razão a Ação está vermelha e entra no alerta.
 * 0,5 é o critério da issue: "progresso abaixo de 50% do esperado".
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

// ─── Avaliação ──────────────────────────────────────────────────────────────

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
  /** realizado ÷ esperado. `null` quando algum dos dois falta. */
  razao: number | null;
  /** Datas efetivamente usadas — a UI mostra quando vieram da Meta. */
  periodo: Periodo;
  /** true quando a Ação não tem datas próprias e herdou as da Meta. */
  periodoHerdado: boolean;
};

const DIA_MS = 24 * 60 * 60 * 1000;

/**
 * Fração do período já decorrida, em 0–100.
 *
 * `null` quando falta alguma das pontas ou o período é degenerado (fim antes
 * do início) — sem denominador não há proporção a calcular.
 */
export function percentualEsperado(
  periodo: Periodo,
  hoje: Date = new Date(),
): number | null {
  const inicio = parseDateOnly(periodo.data_inicio);
  const fim = parseDateOnly(periodo.data_fim);
  if (!inicio || !fim) return null;

  // O período é fechado nas duas pontas: uma Ação de 01/01 a 01/01 dura um dia,
  // e no dia 01/01 ela já está 100% vencida.
  const total = fim.getTime() - inicio.getTime() + DIA_MS;
  if (total <= 0) return null;

  const decorrido = hoje.getTime() - inicio.getTime();
  const bruto = (decorrido / total) * 100;
  return Math.min(100, Math.max(0, bruto));
}

/** Datas da Ação, caindo para as da Meta quando a Ação não tem as suas. */
function periodoEfetivo(
  acao: Acao,
  meta: Periodo | null,
): { periodo: Periodo; herdado: boolean } {
  if (acao.data_inicio && acao.data_fim) {
    return {
      periodo: { data_inicio: acao.data_inicio, data_fim: acao.data_fim },
      herdado: false,
    };
  }
  if (meta?.data_inicio && meta?.data_fim) {
    return {
      periodo: { data_inicio: meta.data_inicio, data_fim: meta.data_fim },
      herdado: true,
    };
  }
  return {
    periodo: { data_inicio: acao.data_inicio, data_fim: acao.data_fim },
    herdado: false,
  };
}

/**
 * Classifica uma Ação no semáforo.
 *
 * A ordem dos casos importa — cada um tira do caminho uma situação em que a
 * razão realizado/esperado não significaria nada:
 *
 * 1. sem quantidade planejada  → sem-dado (0/0 não é 0%)
 * 2. entrega completa          → verde, mesmo fora do prazo: está feito
 * 3. período não conhecido     → sem-dado (nada contra o que comparar)
 * 4. período ainda não começou → verde (esperado 0; nada devido ainda)
 * 5. demais                    → razão contra os limiares
 *
 * Ação com prazo vencido e entrega incompleta cai naturalmente no caso 5 com
 * esperado = 100, então a razão vira o próprio percentual realizado.
 *
 * `hoje` é injetável para manter a função pura e testável.
 */
export function avaliarAcao(
  acao: Acao,
  meta: Periodo | null = null,
  hoje: Date = new Date(),
): AvaliacaoSemaforo {
  const { periodo, herdado } = periodoEfetivo(acao, meta);
  const esperado = percentualEsperado(periodo, hoje);
  const { percentual: realizado } = progressoAcao(acao);

  const base = { realizado, esperado, periodo, periodoHerdado: herdado };

  if (realizado === null) return { ...base, nivel: "sem-dado", razao: null };
  if (realizado >= 100) return { ...base, nivel: "verde", razao: null };
  if (esperado === null) return { ...base, nivel: "sem-dado", razao: null };
  if (esperado <= 0) return { ...base, nivel: "verde", razao: null };

  const razao = realizado / esperado;
  const nivel: NivelSemaforo =
    razao >= LIMIAR_VERDE
      ? "verde"
      : razao >= LIMIAR_VERMELHO
        ? "amarelo"
        : "vermelho";

  return { ...base, nivel, razao };
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
