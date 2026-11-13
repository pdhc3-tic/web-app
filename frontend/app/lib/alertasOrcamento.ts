import { apiClient } from "./api";
import type { NivelSemaforo } from "./semaforo";

/**
 * Alertas orçamentários (#403, backend AJ-BE-07 / PR #414):
 * `GET /sgp/orcamento/alertas/`, já no escopo do perfil. Quem não tem acesso ao
 * orçamento recebe 403, e o painel some em vez de mostrar erro.
 */

export type TipoAlerta = "semaforo" | "subexecucao" | "remanejamento_excessivo";
export type FaixaAlerta = "amarelo" | "vermelho" | "subexecucao" | "devolucao";
export type EscopoAlerta = "limite" | "pool" | "meta" | "submeta" | "acao";

/** `BudgetAlertSerializer`. */
export type AlertaOrcamento = {
  id: number;
  tipo: TipoAlerta;
  escopo: EscopoAlerta;
  referencia_id: number;
  rubrica: number | null;
  rubrica_nome: string | null;
  /** Vazio quando o tipo não tem faixa. */
  faixa: FaixaAlerta | "";
  percentual_atingido: string;
  criado_em: string;
  alertado_em: string;
  resolvido_em: string | null;
};

export type PaginaDeAlertas = { count: number; results: AlertaOrcamento[] };

export type FiltrosDeAlerta = { tipo: TipoAlerta | ""; faixa: FaixaAlerta | "" };

export const TIPO_ALERTA_LABEL: Record<TipoAlerta, string> = {
  semaforo: "Semáforo",
  subexecucao: "Subexecução",
  remanejamento_excessivo: "Remanejamento excessivo",
};

export const FAIXA_ALERTA_LABEL: Record<FaixaAlerta, string> = {
  amarelo: "Amarelo",
  vermelho: "Vermelho",
  subexecucao: "Subexecução",
  devolucao: "Devolução",
};

export const ESCOPO_ALERTA_LABEL: Record<EscopoAlerta, string> = {
  limite: "Limite de gasto",
  pool: "Pool",
  meta: "Meta",
  submeta: "Submeta",
  acao: "Ação",
};

/** Quantos alertas o painel mostra de cada vez. */
export const ALERTAS_POR_PAGINA = 10;

/**
 * GET /api/v1/sgp/orcamento/alertas/?tipo=&faixa=&abertos=true — só os abertos,
 * do mais recente ao mais antigo (a ordem é do backend).
 */
export async function fetchAlertas(
  params: FiltrosDeAlerta & { offset?: number; limit?: number },
  signal?: AbortSignal,
): Promise<PaginaDeAlertas> {
  const qs = new URLSearchParams({
    abertos: "true",
    limit: String(params.limit ?? ALERTAS_POR_PAGINA),
  });
  if (params.offset) qs.set("offset", String(params.offset));
  if (params.tipo) qs.set("tipo", params.tipo);
  if (params.faixa) qs.set("faixa", params.faixa);
  const res = await apiClient(`/api/v1/sgp/orcamento/alertas/?${qs}`, { signal });
  return res.json();
}

/**
 * Cor do selo: amarelo e vermelho são as faixas do semáforo. Subexecução pede
 * atenção e devolução é o caso grave (o recurso volta se não for executado).
 */
export function nivelDoAlerta(alerta: Pick<AlertaOrcamento, "faixa">): NivelSemaforo {
  if (alerta.faixa === "vermelho" || alerta.faixa === "devolucao") return "vermelho";
  if (alerta.faixa === "amarelo" || alerta.faixa === "subexecucao") return "amarelo";
  return "sem-dado";
}

/** "Pool · Diárias" ou "Meta #3": o que o alerta aponta, sem consulta extra. */
export function alvoDoAlerta(alerta: Pick<AlertaOrcamento, "escopo" | "referencia_id" | "rubrica_nome">): string {
  const escopo = ESCOPO_ALERTA_LABEL[alerta.escopo] ?? alerta.escopo;
  return alerta.rubrica_nome ? `${escopo} · ${alerta.rubrica_nome}` : `${escopo} #${alerta.referencia_id}`;
}
