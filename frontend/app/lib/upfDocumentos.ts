import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import {
  requestUploadUrl,
  uploadToStorage,
} from "@/app/components/sgp/PhotoUploader/photoUpload";

// ─── Constantes espelhadas do backend ────────────────────────────────────────

/** Espelha apps/sgp/models/upf_document.py::UPFDocument.TIPO_CHOICES. */
export const TIPO_DOC_OPTIONS = [
  { value: "dap_caf", label: "DAP/CAF" },
  { value: "contrato", label: "Contrato" },
  { value: "laudo", label: "Laudo" },
  { value: "identidade", label: "Identidade" },
  { value: "outro", label: "Outro" },
] as const;

export type TipoDocumento = (typeof TIPO_DOC_OPTIONS)[number]["value"];

/** Espelha apps/sgp/views/upf_documentos.py::ALLOWED_DOCUMENT_CONTENT_TYPES. */
export const ACCEPTED_CONTENT_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
] as const;

export type ContentType = (typeof ACCEPTED_CONTENT_TYPES)[number];

/** Espelha MAX_DOCUMENT_SIZE (10 MB) da mesma view. */
export const MAX_DOC_SIZE_BYTES = 10 * 1024 * 1024;

/** Documentos usam a LimitOffsetPagination padrão do DRF (PAGE_SIZE=10). */
const LIMITE_DOCUMENTOS = 100;

/** Rótulo humano de um tipo de documento (ou o próprio valor, se desconhecido). */
export function tipoDocumentoLabel(tipo: string): string {
  return TIPO_DOC_OPTIONS.find((o) => o.value === tipo)?.label ?? tipo;
}

// ─── Tipos ───────────────────────────────────────────────────────────────────

/** Espelha apps/sgp/serializers.py::UPFDocumentSerializer (leitura). */
export type Documento = {
  id: number;
  tipo: TipoDocumento;
  descricao: string;
  nome_original: string;
  content_type: string;
  tamanho_bytes: number;
  data_documento: string;
  criado_em: string;
  criado_por: string;
};

/** Campos que a UI coleta para gravar o documento após o upload. */
export type DocumentoWritePayload = {
  tipo: TipoDocumento;
  descricao: string;
  data_documento: string;
  nome_original: string;
  content_type: string;
  tamanho_bytes: number;
};

export type UploadHandle = {
  promise: Promise<Documento>;
  abort: () => void;
};

// ─── API ─────────────────────────────────────────────────────────────────────

/** GET /api/v1/upfs/{upfId}/documentos/ — documentos anexados à UPF. */
export async function listDocumentos(
  upfId: string,
  signal?: AbortSignal,
): Promise<Documento[]> {
  const res = await apiClient(
    `/api/v1/upfs/${upfId}/documentos/?limit=${LIMITE_DOCUMENTOS}`,
    { signal },
  );
  const data: Paginated<Documento> = await res.json();
  return data.results;
}

/** DELETE /api/v1/upfs/{upfId}/documentos/{id}/ — remove o documento e o objeto no storage. */
export async function deleteDocumento(upfId: string, id: number): Promise<void> {
  await apiClient(`/api/v1/upfs/${upfId}/documentos/${id}/`, { method: "DELETE" });
}

/**
 * Envia um documento em três etapas — pedir a URL pré-assinada, subir o arquivo
 * (é aqui que o progresso é reportado) e confirmar no backend, que só então cria
 * o UPFDocument. `abort()` interrompe o PUT e impede a confirmação.
 */
export function uploadDocumento(
  upfId: string,
  file: File,
  payload: Omit<
    DocumentoWritePayload,
    "nome_original" | "content_type" | "tamanho_bytes"
  >,
  onProgress: (percent: number) => void,
): UploadHandle {
  const controller = new AbortController();

  async function executar(): Promise<Documento> {
    const { url, key } = await requestUploadUrl(
      `/api/v1/upfs/${upfId}/documentos/upload-url/`,
      { name: file.name, type: file.type, size: file.size },
    );

    await uploadToStorage(url, file, file.type, onProgress, controller.signal);

    if (controller.signal.aborted) {
      throw new DOMException("Upload cancelado.", "AbortError");
    }

    const res = await apiClient(`/api/v1/upfs/${upfId}/documentos/`, {
      method: "POST",
      body: JSON.stringify({
        key,
        nome_original: file.name,
        tipo: payload.tipo,
        descricao: payload.descricao,
        data_documento: payload.data_documento,
      }),
    });
    return res.json();
  }

  return {
    promise: executar(),
    abort: () => controller.abort(),
  };
}

/**
 * Baixa o documento. O backend devolve uma URL pré-assinada de leitura; tentamos
 * buscá-la como blob para preservar o nome original do arquivo e, se o storage
 * não permitir a leitura cross-origin, abrimos a URL em nova aba.
 */
export async function downloadDocumento(
  upfId: string,
  doc: Documento,
): Promise<void> {
  const res = await apiClient(
    `/api/v1/upfs/${upfId}/documentos/${doc.id}/download/`,
  );
  const { url } = (await res.json()) as { url: string; expires_in: number };

  try {
    const arquivo = await fetch(url);
    if (!arquivo.ok) throw new Error("Falha ao baixar o arquivo.");
    const blob = await arquivo.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = doc.nome_original;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
