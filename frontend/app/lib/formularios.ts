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
  /**
   * Restringe às respostas anônimas (respondente NULL no BE). Mutuamente
   * exclusivo com `respondente` — o container zera a busca quando este liga.
   */
  apenas_anonimas?: boolean;
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
  if (params.apenas_anonimas) {
    qs.set("respondente_isnull", "true");
  } else if (params.respondente) {
    qs.set("respondente", params.respondente);
  }
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

/**
 * Teto de uma varredura: `HistoricoPagination.max_page_size` no backend
 * (apps/sgp/pagination.py). Pedir mais que isso é silenciosamente reduzido.
 */
const OPCOES_PAGE_SIZE = 200;

/** Par `{formulario_id, formulario_nome}` para o select da aba Formulários. */
export type FormularioRespondidoOption = {
  formulario_id: number;
  formulario_nome: string;
};

/**
 * Formulários com ao menos uma resposta nesta UPF, para popular o filtro.
 *
 * Não existe endpoint de "formulários distintos por UPF" (a BE-18 lista os
 * disponíveis para *novo* preenchimento, que é outra coisa: um formulário
 * despublicado sai de lá e continua no histórico). Enquanto ele não vem,
 * varremos a listagem **sem filtro**, no maior page_size que o backend aceita,
 * e deduplicamos por `formulario_id` — uma requisição, independente da página
 * que a tabela estiver exibindo.
 *
 * Limite conhecido: UPF com mais de 200 respostas pode deixar de fora um
 * formulário que só apareça depois desse corte. Na prática nenhuma chega
 * perto; a solução definitiva é o endpoint pedido em
 * docs/pendencias-backend-sprint-8.md.
 */
export async function listFormulariosRespondidos(
  upfId: string | number,
  signal?: AbortSignal,
): Promise<FormularioRespondidoOption[]> {
  const data = await listFormResponses(
    upfId,
    { page: 1, page_size: OPCOES_PAGE_SIZE },
    signal,
  );

  const porId = new Map<number, string>();
  for (const r of data.results) {
    if (!porId.has(r.formulario_id)) porId.set(r.formulario_id, r.formulario_nome);
  }
  return Array.from(porId, ([formulario_id, formulario_nome]) => ({
    formulario_id,
    formulario_nome,
  })).sort((a, b) =>
    a.formulario_nome.localeCompare(b.formulario_nome, "pt-BR"),
  );
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

// ─── BE-20: exportação de respostas (CSV/PDF) ───────────────────────────────

export type FormatoExportRespostas = "csv" | "pdf";

/**
 * Teto de espera do lado do cliente. Mesmo racional do BE-9 (plano de trabalho):
 * a view é síncrona, e um pendurado sem timeout deixa o botão girando pra
 * sempre. 60s = mesmo `proxy_read_timeout` do nginx.
 */
export const EXPORT_RESPOSTAS_TIMEOUT_MS = 60_000;

export class ExportRespostasTimeoutError extends Error {
  constructor() {
    super("A geração do arquivo excedeu o tempo limite.");
    this.name = "ExportRespostasTimeoutError";
  }
}

/**
 * Lê o nome do arquivo do `Content-Disposition`. Em dev o header pode não
 * chegar (CORS_EXPOSE_HEADERS não configurado no Django); em prod vem OK.
 */
function nomeDoContentDisposition(header: string | null): string | null {
  if (!header) return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  if (!match) return null;
  const bruto = match[1].trim();
  try {
    return decodeURIComponent(bruto);
  } catch {
    return bruto;
  }
}

/** Fallback quando o header não veio ou é ilegível. */
function nomeDerivadoLocalmente(
  upfId: string | number,
  formato: FormatoExportRespostas,
): string {
  const agora = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const stamp = [
    agora.getFullYear(),
    pad(agora.getMonth() + 1),
    pad(agora.getDate()),
    pad(agora.getHours()),
    pad(agora.getMinutes()),
    pad(agora.getSeconds()),
  ].join("-");
  return `respostas_formularios_upf_${upfId}_${stamp}.${formato}`;
}

function dispararDownload(blob: Blob, nome: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/**
 * GET /api/v1/sgp/upfs/{upfId}/formularios/exportar/?formato=csv|pdf&<filtros>
 *
 * Envia os mesmos filtros da listagem (BE-16 e BE-20 compartilham o
 * `FormResponseFilter`). Não paginado — o arquivo cobre TODAS as respostas
 * que passam pelo filtro, coerente com o critério da issue.
 *
 * Retorna o nome do arquivo entregue (útil para o toast).
 */
export async function exportarRespostasFormularios(
  upfId: string | number,
  filtros: Omit<ListFormResponsesParams, "page" | "page_size"> & {
    formato: FormatoExportRespostas;
  },
): Promise<string> {
  const { formato, ...resto } = filtros;
  const qs = new URLSearchParams({ formato });
  if (resto.formulario_id !== undefined) {
    qs.set("formulario_id", String(resto.formulario_id));
  }
  if (resto.data_inicio) qs.set("data_inicio", resto.data_inicio);
  if (resto.data_fim) qs.set("data_fim", resto.data_fim);
  if (resto.apenas_anonimas) {
    qs.set("respondente_isnull", "true");
  } else if (resto.respondente) {
    qs.set("respondente", resto.respondente);
  }

  let res: Response;
  try {
    res = await apiClient(
      `/api/v1/sgp/upfs/${upfId}/formularios/exportar/?${qs.toString()}`,
      { signal: AbortSignal.timeout(EXPORT_RESPOSTAS_TIMEOUT_MS) },
    );
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") {
      throw new ExportRespostasTimeoutError();
    }
    throw e;
  }

  const nome =
    nomeDoContentDisposition(res.headers.get("Content-Disposition")) ??
    nomeDerivadoLocalmente(upfId, formato);

  dispararDownload(await res.blob(), nome);
  return nome;
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
