/**
 * Cliente do endpoint de calendário do SGP (BE-3, Issue #126). Payload reduzido
 * de atividades cujo intervalo (data_inicio..data_fim) intersecciona o período
 * solicitado. Máximo de 90 dias — a UI deve limitar a janela de consulta.
 *
 * Fonte: apps/sgp/serializers.py::ActivityCalendarioSerializer.
 */
import { apiClient } from "@/app/lib/api";
import type { Refinar, Schema } from "@/app/lib/apiSchema";

// ── Tipos ────────────────────────────────────────────────────────────────────

/**
 * Os tipos vêm do schema (#273).
 */

/** Objeto aninhado leve devolvido pelo serializer do calendário. */
export type CalendarNestedRef = {
  id: number;
  nome: string;
};

/**
 * `ActivityCalendarioSerializer` — evento do calendário.
 *
 * Refinamentos: `tipo_atividade` e `status` passam dos enums estreitos do
 * schema para `string`, compatível com o restante do código.
 */
export type CalendarActivityEvent = Refinar<
  Schema<"ActivityCalendario">,
  {
    tipo_atividade: string;
    status: string;
  }
>;

/** `ActivityCalendarioResposta`. */
export type CalendarResponse = Schema<"ActivityCalendarioResposta">;

// ── Query ────────────────────────────────────────────────────────────────────

export type CalendarQueryParams = {
  /** YYYY-MM-DD, obrigatório. */
  inicio: string;
  /** YYYY-MM-DD, obrigatório. Máx. 90 dias após inicio. */
  fim: string;
  tecnico?: string;
  projeto?: string;
  acao?: string;
  tipo?: string;
  status?: string;
};

/**
 * Monta a query string do calendário. Os nomes dos filtros seguem os
 * parâmetros aceitos pelo endpoint (`tecnico_id`, `projeto`, `acao`,
 * `tipo_atividade`, `status`) — o mapeamento acontece aqui para os chamadores
 * poderem usar os mesmos nomes da listagem.
 */
function buildCalendarQuery(params: CalendarQueryParams): string {
  const qs = new URLSearchParams();
  qs.set("inicio", params.inicio);
  qs.set("fim", params.fim);
  if (params.tecnico) qs.set("tecnico_id", params.tecnico);
  if (params.projeto) qs.set("projeto", params.projeto);
  if (params.acao) qs.set("acao", params.acao);
  if (params.tipo) qs.set("tipo_atividade", params.tipo);
  if (params.status) qs.set("status", params.status);
  return qs.toString();
}

/** GET /api/v1/sgp/atividades/calendario/ — sem paginação, até 90 dias. */
export async function listCalendarActivities(
  params: CalendarQueryParams,
  signal?: AbortSignal,
): Promise<CalendarResponse> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/calendario/?${buildCalendarQuery(params)}`,
    { signal },
  );
  return res.json();
}
