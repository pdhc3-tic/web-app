import { ApiError, apiClient } from "@/app/lib/api";
import type { BadgeStatus } from "@/app/components/ui/Badge/Badge";
import type { Demanda, SolicitacaoDemanda } from "@/app/lib/demandas";
import { bloqueiosDaSubmissao, type BloqueioSolicitacao } from "@/app/lib/solicitacoes";

/**
 * SGD — Recurso extra e Fila de Remanejamentos (#321, BE-12).
 *
 * O pedido percorre a máquina de estados de `BudgetIncreaseRequest` (SGP §6.6):
 * o solicitante pede → o Articulador Estadual emite parecer ou devolve → a UGP
 * aprova, aprova parcialmente ou recusa. Aprovar eleva o limite individual do
 * solicitante; a demanda bloqueada NÃO é submetida sozinha — o solicitante
 * submete de novo.
 *
 * Tipos escritos à mão, espelhando `apps/sgd/serializers/remanejamento.py`.
 */

// ─── Tipos ───────────────────────────────────────────────────────────────────

/** Espelha `BudgetIncreaseRequest.Status`. */
export type StatusPedido =
  | "rascunho"
  | "submetida"
  | "devolvida"
  | "com_parecer"
  | "aprovada"
  | "aprovada_parcialmente"
  | "recusada";

export type DecisaoPedido = "aprovar" | "aprovar_parcialmente" | "recusar";

/** `BudgetIncreaseRequestSerializer`. Valores monetários vêm como string decimal. */
export type PedidoRecursoExtra = {
  id: number;
  user: number;
  solicitante_nome: string;
  /** Slug da rubrica. */
  rubrica: string;
  rubrica_nome: string;
  valor_solicitado: string;
  valor_aprovado: string | null;
  periodo_aplicacao: string;
  activity: number | null;
  /** Id da demanda como string ("47"); vazio no pedido sem demanda. */
  demanda_id: string;
  justificativa: string;
  status: StatusPedido;
  status_display: string;
  transicoes_permitidas: StatusPedido[];
  parecer_articulador: string;
  parecer_por: number | null;
  parecer_por_nome: string | null;
  justificativa_decisao: string;
  decidido_por: number | null;
  decidido_por_nome: string | null;
  decidido_em: string | null;
  criado_em: string;
  atualizado_em: string;
};

/** Resposta de `decidir`: o pedido e o remanejamento que a aprovação disparou, se houve. */
export type PedidoDecidido = PedidoRecursoExtra & { transferencia_id: number | null };

export const STATUS_PEDIDO_TERMINAIS: StatusPedido[] = [
  "aprovada",
  "aprovada_parcialmente",
  "recusada",
];

const BADGE_POR_STATUS: Record<StatusPedido, BadgeStatus> = {
  rascunho: "planejado",
  submetida: "agendado",
  devolvida: "adiada",
  com_parecer: "sem-evidencia",
  aprovada: "concluido",
  aprovada_parcialmente: "concluido",
  recusada: "nao-realizada",
};

export function badgeStatusDoPedido(status: StatusPedido): BadgeStatus {
  return BADGE_POR_STATUS[status] ?? "planejado";
}

// ─── API ─────────────────────────────────────────────────────────────────────

const REMANEJAMENTOS_PATH = "/api/v1/sgd/remanejamentos/";

/** `RemanejamentoPagination.max_limit`. */
const LIMITE_LISTA_PEDIDOS = 100;

export type ListaPedidos = {
  pedidos: PedidoRecursoExtra[];
  /** Total no backend com os mesmos filtros; maior que `pedidos.length` = lista parcial. */
  total: number;
};

/**
 * GET /api/v1/sgd/remanejamentos/ — já no escopo do perfil (`pedidos_visiveis`):
 * UGP, FGD e Super Admin veem tudo; o Articulador, os pedidos dos seus estados;
 * os demais, só os próprios.
 *
 * - `status`: repetido, o backend devolve a união. Sem `status`, a UGP recebe só
 *   os Com parecer; `"todos"` desliga o filtro para qualquer perfil.
 * - `demanda`: só os pedidos daquela demanda.
 */
export async function listPedidos(
  params: { status?: (StatusPedido | "todos")[]; demanda?: number } = {},
  signal?: AbortSignal,
): Promise<ListaPedidos> {
  const qs = new URLSearchParams();
  for (const st of params.status ?? []) qs.append("status", st);
  if (params.demanda !== undefined) qs.set("demanda", String(params.demanda));
  qs.set("limit", String(LIMITE_LISTA_PEDIDOS));
  const res = await apiClient(`${REMANEJAMENTOS_PATH}?${qs}`, { signal });
  const pagina = (await res.json()) as { count: number; results: PedidoRecursoExtra[] };
  return { pedidos: pagina.results, total: pagina.count };
}

/** GET /api/v1/sgd/remanejamentos/{id}/ */
export async function getPedido(id: number | string, signal?: AbortSignal): Promise<PedidoRecursoExtra> {
  const res = await apiClient(`${REMANEJAMENTOS_PATH}${id}/`, { signal });
  return res.json();
}

async function postar<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await apiClient(path, { method: "POST", body: JSON.stringify(body) });
  return res.json();
}

/**
 * POST /api/v1/sgd/demandas/{id}/solicitar-recurso-extra/ — o atalho da
 * demanda bloqueada pelo limite individual. Já sai submetido ao Articulador.
 *
 * Sem `valor_solicitado`: o backend assume o que falta no limite individual
 * (`_deficit_individual`). O bloqueio não informa esse valor antes do envio
 * (pendencias-backend-sprint-10.md, item 23), então a tela não o calcula — ele
 * aparece no pedido devolvido.
 */
export function solicitarRecursoExtra(
  demandaId: number,
  params: { rubrica: string; justificativa: string },
): Promise<PedidoRecursoExtra> {
  return postar(`/api/v1/sgd/demandas/${demandaId}/solicitar-recurso-extra/`, params);
}

/** Articulador Estadual: Submetida → Com parecer. */
export const emitirParecer = (id: number, parecer: string) =>
  postar<PedidoRecursoExtra>(`${REMANEJAMENTOS_PATH}${id}/parecer/`, { parecer });

/** Articulador Estadual: Submetida → Devolvida. */
export const devolverPedido = (id: number, justificativa: string) =>
  postar<PedidoRecursoExtra>(`${REMANEJAMENTOS_PATH}${id}/devolver/`, { justificativa });

/** Solicitante: ajusta o pedido Devolvido (PATCH) antes de reenviar. */
export async function editarPedido(
  id: number,
  campos: { justificativa?: string; valor_solicitado?: string },
): Promise<PedidoRecursoExtra> {
  const res = await apiClient(`${REMANEJAMENTOS_PATH}${id}/`, {
    method: "PATCH",
    body: JSON.stringify(campos),
  });
  return res.json();
}

/** Solicitante: Devolvida → Submetida. */
export const reenviarPedido = (id: number) =>
  postar<PedidoRecursoExtra>(`${REMANEJAMENTOS_PATH}${id}/submeter/`, {});

/**
 * UGP e Super Admin, em Com parecer. A justificativa é obrigatória nas três
 * decisões; `valorAprovado`, só na parcial. `origemAllocation`: a alocação
 * estadual ou nacional que cobre o que faltar no pool territorial — o backend
 * recusa a aprovação sem ela quando o pool não cobre (erro em `origem_allocation`).
 */
export function decidirPedido(
  id: number,
  params: {
    decisao: DecisaoPedido;
    justificativa: string;
    valorAprovado?: string;
    origemAllocation?: number | null;
  },
): Promise<PedidoDecidido> {
  const body: Record<string, unknown> = {
    decisao: params.decisao,
    justificativa: params.justificativa,
  };
  if (params.valorAprovado !== undefined) body.valor_aprovado = params.valorAprovado;
  if (params.origemAllocation) body.origem_allocation = params.origemAllocation;
  return postar(`${REMANEJAMENTOS_PATH}${id}/decidir/`, body);
}

/** A mensagem do backend para um campo do 400, se houver. */
export function erroDoCampo(e: unknown, campo: string): string | null {
  if (!(e instanceof ApiError)) return null;
  return e.fieldErrors?.find((f) => f.field === campo)?.message ?? null;
}

// ─── Bloqueio na submissão (#295) ────────────────────────────────────────────

/** O que o fluxo "Solicitar recurso extra" precisa saber do bloqueio. */
export type BloqueioRecursoExtra = {
  solicitacaoId: number;
  rubrica: { slug: string; nome: string };
  /** O que o limite individual ainda comportava e o que a solicitação pedia. */
  disponivel: string;
  solicitado: string;
  /** O que falta na rubrica; null até o backend expor (sprint 10, item 23). */
  valorFaltante: string | null;
};

/**
 * O atalho "Solicitar recurso extra" para uma solicitação barrada na
 * submissão, ou null quando a trava não pede recurso extra — a territorial
 * pede o Articulador.
 */
export function recursoExtraDoBloqueio(
  solicitacao: SolicitacaoDemanda,
  bloqueio: BloqueioSolicitacao | undefined,
): BloqueioRecursoExtra | null {
  if (bloqueio?.acao_sugerida !== "solicitar_recurso_extra") return null;
  return {
    solicitacaoId: solicitacao.id,
    rubrica: { slug: solicitacao.rubrica_slug, nome: solicitacao.rubrica_nome },
    disponivel: bloqueio.disponivel,
    solicitado: bloqueio.solicitado,
    valorFaltante: bloqueio.valor_faltante ?? null,
  };
}

/**
 * Lê o 400 de `POST /sgd/demandas/{id}/submeter/` e devolve o primeiro
 * bloqueio que cabe no atalho "Solicitar recurso extra".
 */
export function bloqueioDeRecursoExtra(erro: unknown, demanda: Demanda): BloqueioRecursoExtra | null {
  const bloqueadas = bloqueiosDaSubmissao(erro);
  if (!bloqueadas) return null;
  for (const solicitacao of demanda.solicitacoes) {
    const atalho = recursoExtraDoBloqueio(solicitacao, bloqueadas[solicitacao.id]);
    if (atalho) return atalho;
  }
  return null;
}
