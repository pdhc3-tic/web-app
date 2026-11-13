import { apiClient, ApiError } from "@/app/lib/api";
import { formatCurrencyBRL } from "@/app/lib/format";

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

/** Corpo do 400 de `_exigir_saldo_na_origem` (`apps/sgp/budget/services.py`). */
type RecusaDeSaldo = { code?: unknown; disponivel?: unknown; solicitado?: unknown };

function saldoDaRecusa(erro: ApiError): string | null {
  const corpo = erro.raw as RecusaDeSaldo | undefined;
  return typeof corpo?.disponivel === "string" ? formatCurrencyBRL(corpo.disponivel) : null;
}

/**
 * A mensagem do erro para a etapa em que ele veio. `INSUFFICIENT_BALANCE` tem
 * dois sentidos: na simulação, o valor passa do saldo da origem; na
 * confirmação, o saldo mudou depois da simulação. O código não vai para a tela.
 */
export function mensagemDeErro(erro: unknown, etapa: "simular" | "confirmar"): string {
  if (erro instanceof ApiError) {
    if (erro.code === "INSUFFICIENT_BALANCE") {
      const disponivel = saldoDaRecusa(erro);
      if (etapa === "simular") {
        return disponivel
          ? `O valor passa do saldo da origem: há ${disponivel} disponível para remanejar.`
          : "O valor passa do saldo da origem.";
      }
      return disponivel
        ? `O saldo da origem mudou desde a simulação e agora é ${disponivel}. Simule de novo antes de confirmar.`
        : "O saldo da origem mudou desde a simulação. Simule de novo antes de confirmar.";
    }
    return erro.message;
  }
  return etapa === "simular"
    ? "Não foi possível simular o remanejamento."
    : "Não foi possível concluir o remanejamento.";
}
