import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/sgp/models/form_response.py::FormResponse.Status. */
export type FormResponseStatus = "rascunho" | "submetido";

/** Espelha apps/sgp/models/form_response.py::FormResponse.Origem. */
export type FormResponseOrigem = "web" | "sca";

/**
 * Espelha apps/sgp/serializers.py::FormResponseListSerializer.
 * `respondente` pode ser `null` — o front rotula como "Anônimo" (critério #178).
 */
export type FormResponseListItem = {
  id: number;
  upf: number;
  formulario_id: number;
  formulario_nome: string;
  formulario_versao: string;
  contract_version: string;
  resposta_id_origem: string;
  data_preenchimento: string;
  respondente: string | null;
  status: FormResponseStatus;
  origem: FormResponseOrigem;
  criado_em: string;
};

/**
 * Estrutura livre do payload recebido do SGF. O contrato só garante ser
 * JSON válido — o modal (#179) renderiza recursivamente, com fallback
 * genérico chave/valor para tipos desconhecidos. Ordem de iteração de
 * `Object.entries` preserva a ordem original de inserção do JSON (ES2015+),
 * o que satisfaz o critério "ordem original das seções/campos".
 */
export type RespostasJsonValor =
  | string
  | number
  | boolean
  | null
  | RespostasJsonValor[]
  | { [chave: string]: RespostasJsonValor };

export type RespostasJson = { [chave: string]: RespostasJsonValor };

/**
 * Espelha FormResponseDetailSerializer — mesmo do list + `respostas_json`.
 */
export type FormResponseDetail = FormResponseListItem & {
  respostas_json: RespostasJson;
};

/** Filtros aceitos pelo endpoint (BE-16). */
export type ListFormResponsesParams = {
  page?: number;
  page_size?: number;
  formulario_id?: number;
  /** YYYY-MM-DD — filtra por data_preenchimento >= data. */
  data_inicio?: string;
  /** YYYY-MM-DD — filtra por data_preenchimento <= data. */
  data_fim?: string;
  /** Busca `icontains` no campo respondente (backend). */
  respondente?: string;
};

// ─── API ────────────────────────────────────────────────────────────────────

function buildQuery(params: ListFormResponsesParams): string {
  const qs = new URLSearchParams();
  if (params.page !== undefined) qs.set("page", String(params.page));
  if (params.page_size !== undefined)
    qs.set("page_size", String(params.page_size));
  if (params.formulario_id !== undefined)
    qs.set("formulario_id", String(params.formulario_id));
  if (params.data_inicio) qs.set("data_inicio", params.data_inicio);
  if (params.data_fim) qs.set("data_fim", params.data_fim);
  if (params.respondente) qs.set("respondente", params.respondente);
  return qs.toString();
}

/**
 * GET /api/v1/sgp/upfs/{upfId}/formularios/ — respostas paginadas da UPF.
 * Endpoint usa PageNumberPagination (HistoricoPagination), não LimitOffset.
 */
export async function listFormResponses(
  upfId: string | number,
  params: ListFormResponsesParams = {},
  signal?: AbortSignal,
): Promise<Paginated<FormResponseListItem>> {
  const qs = buildQuery(params);
  const url = `/api/v1/sgp/upfs/${upfId}/formularios/${qs ? `?${qs}` : ""}`;
  const res = await apiClient(url, { signal });
  return res.json();
}

/** GET /api/v1/sgp/upfs/{upfId}/formularios/{id}/ — resposta + respostas_json. */
export async function getFormResponse(
  upfId: string | number,
  id: string | number,
  signal?: AbortSignal,
): Promise<FormResponseDetail> {
  const res = await apiClient(
    `/api/v1/sgp/upfs/${upfId}/formularios/${id}/`,
    { signal },
  );
  return res.json();
}

// ─── BE-18: formulários publicados que a UPF pode responder ─────────────────

/** Espelha apps/sgp/serializers.py::AvailableFormSerializer. */
export type AvailableForm = {
  id: number;
  nome: string;
  versao: string;
  descricao: string | null;
  atualizado_em: string;
};

/**
 * GET /api/v1/sgp/formularios-disponiveis/ — formulários "publicado" com
 * escopo `upf` e território do usuário (ou globais). Não paginado.
 */
export async function listAvailableForms(
  signal?: AbortSignal,
): Promise<AvailableForm[]> {
  const res = await apiClient(`/api/v1/sgp/formularios-disponiveis/`, {
    signal,
  });
  return res.json();
}
