import { apiClient, ApiError } from "@/app/lib/api";

/**
 * Remanejamento entre pools do orçamento (#402, AJ-FE-06).
 *
 * UGP/Super Admin usam o endpoint para mover saldo entre pools sem seguir a
 * hierarquia de distribuição. O fluxo da tela é simular → confirmar; o
 * backend valida de novo na confirmação e devolve `INSUFFICIENT_BALANCE` se
 * o saldo mudou entre as duas chamadas.
 */

export type NivelSemaforo = "verde" | "amarelo" | "vermelho";

export type ImpactoNoPool = {
  saldo_antes: string;
  saldo_depois: string;
  percentual_antes: string;
  percentual_depois: string;
  percentual_execucao_antes: string;
  percentual_execucao_depois: string;
  faixa_antes: NivelSemaforo;
  faixa_depois: NivelSemaforo;
};

export type SimulacaoRemanejamento = {
  origem: ImpactoNoPool;
  destino: ImpactoNoPool;
};

export type RemanejamentoPayload = {
  origem_allocation: number;
  destino_allocation: number;
  valor: string;
  justificativa: string;
};

/** BudgetTransaction retornada pela confirmação. */
export type LancamentoRemanejamento = {
  id: number;
  pool: number | null;
  spending_limit: number | null;
  allocation: number;
  activity: number | null;
  tipo: string;
  valor: string;
  saldo_anterior: string;
  saldo_posterior: string;
  demanda_id: string | null;
  demand_request_id: string | null;
  justificativa: string;
  criado_por: number | null;
  criado_em: string;
  efeito: string;
  periodo_inicio: string;
  periodo_fim: string;
};

const SIMULAR_PATH = "/api/v1/sgp/orcamento/remanejamentos/simular/";
const CRIAR_PATH = "/api/v1/sgp/orcamento/remanejamentos/";

/**
 * POST .../remanejamentos/simular/ — devolve `SimulacaoRemanejamento` com
 * saldo antes/depois e a faixa do semáforo de origem e destino. Não grava.
 */
export async function simularRemanejamento(
  payload: RemanejamentoPayload,
  signal?: AbortSignal,
): Promise<SimulacaoRemanejamento> {
  const res = await apiClient(SIMULAR_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
  return res.json();
}

/**
 * POST .../remanejamentos/ — grava o remanejamento com o payload exato que foi
 * simulado. O backend relê o saldo; se mudou, devolve 400 com
 * `code: "INSUFFICIENT_BALANCE"`.
 */
export async function confirmarRemanejamento(
  payload: RemanejamentoPayload,
): Promise<LancamentoRemanejamento[]> {
  const res = await apiClient(CRIAR_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/**
 * Lê o `code` do 400 do backend. Se `INSUFFICIENT_BALANCE`, a mensagem padrão
 * explica ao usuário que o saldo mudou e pede nova simulação.
 */
export function mensagemDeErro(erro: unknown): string {
  if (erro instanceof ApiError) {
    if (erro.code === "INSUFFICIENT_BALANCE") {
      return "O saldo mudou entre a simulação e a confirmação (INSUFFICIENT_BALANCE). Simule de novo antes de confirmar.";
    }
    return erro.message;
  }
  return "Não foi possível concluir o remanejamento.";
}
