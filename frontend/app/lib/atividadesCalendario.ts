/**
 * Cliente do endpoint de calendário do SGP (BE-3, Issue #126). Payload reduzido
 * de atividades cujo intervalo (data_inicio..data_fim) intersecciona o período
 * solicitado. Máximo de 90 dias — a UI deve limitar a janela de consulta.
 *
 * Fonte: apps/sgp/serializers.py::ActivityCalendarioSerializer.
 */
import { apiClient } from "@/app/lib/api";

// ── Tipos ────────────────────────────────────────────────────────────────────

/** Objeto aninhado leve devolvido pelo serializer do calendário. */
export type CalendarNestedRef = {
  id: number;
  nome: string;
};

/** Evento do calendário — subset de Activity otimizado para grade. */
export type CalendarActivityEvent = {
  id: number;
  titulo: string;
  tipo_atividade: string;
  tipo_atividade_display: string;
  status: string;
  status_display: string;
  /** True quando data_fim ficou no passado sem chegar a status terminal. */
  atrasada: boolean;
  /** Cor HEX da paleta semântica do design system, derivada do status. */
  cor: string;
  /** YYYY-MM-DD (sem horário — os models são DateField). */
  data_inicio: string;
  data_fim: string;
  tecnico_responsavel: CalendarNestedRef;
  municipio: CalendarNestedRef;
  comunidade: CalendarNestedRef | null;
};

export type CalendarResponse = {
  count: number;
  inicio: string;
  fim: string;
  results: CalendarActivityEvent[];
};

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
