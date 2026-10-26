import { apiClient, ApiError } from "@/app/lib/api";

/**
 * Configuração do mapeamento Arlo ↔ SGD (#320, SGD-FE-9).
 *
 * O CRUD do `ArloFieldMappingViewSet` (BE-9) está em
 * `/api/v1/sgd/config/arlo-mapping/`. Lista, cria, edita, remove e reordena.
 * `direcao` e `campo_sgd` identificam a linha: no PATCH, viram read-only.
 *
 * O que ainda não existe no backend fica anotado em
 * docs/pendencias-backend-sprint-10.md (item 18) e vai pela issue #373:
 *   - `GET /api/v1/sgd/config/arlo-mapping/campos/` — catálogo dos campos SGD
 *     com rótulo, obrigatoriedade e formatos permitidos por direção;
 *   - `GET /api/v1/sgd/config/arlo-mapping/preview/?direcao=exportacao` —
 *     uma linha de exemplo da exportação, com o mapeamento vigente.
 *
 * Enquanto essas rotas não existem, a tela usa o `CAMPOS_FALLBACK` abaixo
 * (fiel ao `apps/sgd/services/arlo_mapping.py`) para o catálogo e um aviso
 * para o preview. Quando o backend responder, as duas funções passam a
 * consumir a rota — nenhum componente muda.
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

/**
 * Catálogo espelhado de `apps/sgd/services/arlo_mapping.py` (verificado contra
 * a `main` em 26/10/2026). É a mesma fonte do backend; portanto, enquanto o
 * endpoint não publicar o catálogo, a tela mantém os campos em sincronia pela
 * revisão de código. Trocar aqui sem o backend saber geraria 400 no POST.
 *
 * O rótulo é escolhido no front — o endpoint ainda não devolve `label`, então
 * aqui ficam os títulos legíveis. Se o backend publicar outros, trocar.
 */
export const CAMPOS_FALLBACK: CatalogoCamposArlo = {
  exportacao: [
    { campo: "demanda_id", label: "ID da demanda", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "solicitacao_id", label: "ID da solicitação", obrigatorio: false, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "titulo", label: "Título", obrigatorio: false, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "meta", label: "Meta", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "submeta", label: "Submeta", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "acao", label: "Ação", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "indicador", label: "Indicador", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "atividade", label: "Atividade", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "rubrica", label: "Rubrica", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "solicitante", label: "Solicitante", obrigatorio: false, formatos: [{ value: "texto", label: "Texto" }] },
    {
      campo: "valor_estimado",
      label: "Valor estimado",
      obrigatorio: false,
      formatos: [{ value: "texto", label: "Texto" }, { value: "moeda", label: "Moeda" }],
    },
    {
      campo: "valor_autorizado",
      label: "Valor autorizado",
      obrigatorio: false,
      formatos: [{ value: "texto", label: "Texto" }, { value: "moeda", label: "Moeda" }],
    },
  ],
  importacao: [
    { campo: "demanda_id", label: "ID da demanda", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "solicitacao_id", label: "ID da solicitação", obrigatorio: false, formatos: [{ value: "texto", label: "Texto" }] },
    { campo: "numero_processo", label: "Número do processo", obrigatorio: true, formatos: [{ value: "texto", label: "Texto" }] },
    {
      campo: "data_pagamento",
      label: "Data do pagamento",
      obrigatorio: true,
      formatos: [{ value: "data", label: "Data" }],
    },
    {
      campo: "valor_pago",
      label: "Valor pago",
      obrigatorio: true,
      formatos: [{ value: "moeda", label: "Moeda" }],
    },
    { campo: "comprovante", label: "Comprovante", obrigatorio: false, formatos: [{ value: "texto", label: "Texto" }] },
  ],
};

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

/**
 * GET catálogo dos campos — pendência do backend. Enquanto 404, cai no
 * fallback do serviço (mesma fonte do backend). Quando o endpoint existir,
 * nenhum chamador muda.
 */
export async function fetchCamposArloMapping(
  signal?: AbortSignal,
): Promise<CatalogoCamposArlo> {
  try {
    const res = await apiClient(`${PATH}campos/`, { signal });
    return res.json();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return CAMPOS_FALLBACK;
    throw e;
  }
}

/** Linha do preview da exportação — uma coluna no cabeçalho e um valor. */
export type ArloMappingPreview = {
  colunas: string[];
  linha: (string | number | null)[];
};

/**
 * GET preview da exportação — pendência do backend (item 18 do doc da sprint
 * 10, repetido no #373). Enquanto a rota não existe, devolve `null` para a
 * tela mostrar o aviso de pendência. Quando o endpoint existir, o chamador
 * passa a receber a linha.
 */
export async function fetchPreviewArloMapping(
  direcao: DirecaoArlo,
  signal?: AbortSignal,
): Promise<ArloMappingPreview | null> {
  try {
    const res = await apiClient(`${PATH}preview/?direcao=${direcao}`, {
      signal,
    });
    return res.json();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
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
