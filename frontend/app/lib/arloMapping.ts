import { apiClient, type ApiError } from "@/app/lib/api";

/**
 * Configuração do mapeamento Arlo ↔ SGD (#320, SGD-FE-9), sobre o
 * `ArloFieldMappingViewSet` (BE-9) em `/api/v1/sgd/config/arlo-mapping/`:
 * lista, cria, edita, remove e reordena; `campos/` publica o catálogo dos
 * campos por direção e `preview/` monta uma linha de exemplo da exportação.
 * `direcao` e `campo_sgd` identificam a linha: no PATCH, viram read-only.
 */

const PATH = "/api/v1/sgd/config/arlo-mapping/";

export type DirecaoArlo = "exportacao" | "importacao";
export type FormatoArlo = "texto" | "data" | "moeda";

export type ArloFieldMapping = {
  id: number;
  direcao: DirecaoArlo;
  campo_sgd: string;
  coluna_arlo: string;
  formato: FormatoArlo;
  ordem: number;
  ativo: boolean;
};

export type ArloFieldMappingWritePayload = {
  direcao: DirecaoArlo;
  campo_sgd: string;
  coluna_arlo: string;
  formato: FormatoArlo;
  ativo?: boolean;
};

export type ArloFieldMappingUpdatePayload = {
  coluna_arlo?: string;
  formato?: FormatoArlo;
  ativo?: boolean;
};

/** Metadado de um campo do SGD mapeável para a planilha do Arlo. */
export type CampoArlo = {
  campo: string;
  label: string;
  obrigatorio: boolean;
  formatos: { value: FormatoArlo; label: string }[];
};

export type CatalogoCamposArlo = Record<DirecaoArlo, CampoArlo[]>;

/** GET /api/v1/sgd/config/arlo-mapping/?direcao= — lista por direção, ordenada. */
export async function listArloMapping(
  direcao: DirecaoArlo,
  signal?: AbortSignal,
): Promise<ArloFieldMapping[]> {
  const res = await apiClient(`${PATH}?direcao=${direcao}`, { signal });
  const data: ArloFieldMapping[] = await res.json();
  // O backend já ordena por (direcao, ordem, pk); duplicamos para não depender
  // da ordenação se o endpoint ganhar paginação no futuro.
  return [...data].sort((a, b) => a.ordem - b.ordem || a.id - b.id);
}

/** POST — cria uma linha. `ordem` é definida pelo backend quando omitida. */
export async function createArloMapping(
  payload: ArloFieldMappingWritePayload,
): Promise<ArloFieldMapping> {
  const res = await apiClient(PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH — edita coluna, formato e ativo. Direção e campo_sgd são read-only. */
export async function updateArloMapping(
  id: number,
  payload: ArloFieldMappingUpdatePayload,
): Promise<ArloFieldMapping> {
  const res = await apiClient(`${PATH}${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** DELETE — remove. Backend recusa se deixaria a direção sem um obrigatório. */
export async function deleteArloMapping(id: number): Promise<void> {
  await apiClient(`${PATH}${id}/`, { method: "DELETE" });
}

/**
 * POST reordenar — grava `ordem` em sequência conforme `ids`. O backend
 * exige `ids` com TODAS as linhas da direção (sem repetição) e devolve a
 * lista já ordenada.
 */
export async function reordenarArloMapping(
  direcao: DirecaoArlo,
  ids: number[],
): Promise<ArloFieldMapping[]> {
  const res = await apiClient(`${PATH}reordenar/`, {
    method: "POST",
    body: JSON.stringify({ direcao, ids }),
  });
  return res.json();
}

/** GET campos/ — catálogo dos campos do SGD por direção, com rótulo, obrigatoriedade e formatos. */
export async function fetchCamposArloMapping(
  signal?: AbortSignal,
): Promise<CatalogoCamposArlo> {
  const res = await apiClient(`${PATH}campos/`, { signal });
  return res.json();
}

/** `PreviewExportacaoArloSerializer`: o cabeçalho e uma linha do CSV, já formatada. */
export type ArloMappingPreview = {
  colunas: string[];
  linha: string[];
};

/** GET preview/?direcao=exportacao — a linha de exemplo com o mapeamento vigente. */
export async function fetchPreviewArloMapping(
  direcao: DirecaoArlo,
  signal?: AbortSignal,
): Promise<ArloMappingPreview> {
  const res = await apiClient(`${PATH}preview/?direcao=${direcao}`, { signal });
  return res.json();
}

export const DIRECAO_LABEL: Record<DirecaoArlo, string> = {
  exportacao: "Exportação (SGD → Arlo)",
  importacao: "Importação (Arlo → SGD)",
};

export const FORMATO_LABEL: Record<FormatoArlo, string> = {
  texto: "Texto",
  data: "Data",
  moeda: "Moeda",
};

/**
 * Mensagem amigável a partir do erro do backend. O `ArloFieldMappingSerializer`
 * devolve mensagens em pt-BR via `serializers.ValidationError`, com os codes
 * padrão do DRF; o `validar_ativos_obrigatorios` devolve um `ValidationError`
 * global quando a mudança deixaria a direção sem um obrigatório.
 */
export function mensagemErroArloMapping(e: ApiError): string {
  if (e.status === 403) return "Você não tem permissão para esta ação.";
  if (e.fieldErrors && e.fieldErrors.length > 0) {
    return e.fieldErrors.map((fe) => fe.message).join(" ");
  }
  return e.message || "Não foi possível concluir a operação.";
}
