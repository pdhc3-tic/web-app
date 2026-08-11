/**
 * Camada de acesso aos endpoints de evidências (fotos + documentos) de uma
 * atividade. Segue o mesmo fluxo em duas etapas do PhotoUploader:
 *   upload-url → PUT direto no R2 (com progresso) → confirm.
 */
import { apiClient } from "@/app/lib/api";
import {
  uploadToStorage as uploadBlobToStorage,
  type UploadUrlResponse,
} from "@/app/components/sgp/PhotoUploader/photoUpload";
import type {
  EvidenceDocument,
  EvidencePhoto,
  TipoDocumentoAtividade,
} from "./types";

// Reexport para consumidores que só usam esta camada.
export { uploadBlobToStorage };
export type { UploadUrlResponse };

// ── Fotos ────────────────────────────────────────────────────────────────────

export type PhotoUploadUrlPayload = {
  filename: string;
  content_type: string;
  size: number;
  legenda?: string;
  data_hora_captura?: string | null;
  latitude?: string | null;
  longitude?: string | null;
};

export type PhotoConfirmPayload = {
  key: string;
  legenda?: string;
  data_hora_captura?: string | null;
  latitude?: string | null;
  longitude?: string | null;
};

export async function listPhotos(
  atividadeId: string,
  signal?: AbortSignal,
): Promise<EvidencePhoto[]> {
  const res = await apiClient(`/api/v1/sgp/atividades/${atividadeId}/fotos/`, {
    signal,
  });
  return res.json();
}

export async function requestPhotoUploadUrl(
  atividadeId: string,
  payload: PhotoUploadUrlPayload,
): Promise<UploadUrlResponse> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/fotos/upload-url/`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return res.json();
}

export async function confirmPhoto(
  atividadeId: string,
  payload: PhotoConfirmPayload,
): Promise<EvidencePhoto> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/fotos/confirm/`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return res.json();
}

export async function deletePhoto(
  atividadeId: string,
  fotoId: number,
): Promise<void> {
  await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/fotos/${fotoId}/`,
    { method: "DELETE" },
  );
}

/**
 * Atualiza campos editáveis inline da foto (legenda por ora). O backend precisa
 * expor PATCH /fotos/{id}/ — se não estiver disponível, o apiClient devolve
 * ApiError e a UI mostra um toast de erro para o usuário.
 */
export async function updatePhoto(
  atividadeId: string,
  fotoId: number,
  patch: Partial<Pick<EvidencePhoto, "legenda">>,
): Promise<EvidencePhoto> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/fotos/${fotoId}/`,
    { method: "PATCH", body: JSON.stringify(patch) },
  );
  return res.json();
}

/** Envia a nova ordem completa; o índice 0 vira a foto de capa. */
export async function reorderPhotos(
  atividadeId: string,
  ids: number[],
): Promise<EvidencePhoto[]> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/fotos/reordenar/`,
    { method: "PATCH", body: JSON.stringify({ ids }) },
  );
  return res.json();
}

// ── Documentos ───────────────────────────────────────────────────────────────

export type DocumentUploadUrlPayload = {
  filename: string;
  content_type: string;
  size: number;
};

export type DocumentConfirmPayload = {
  key: string;
  tipo: TipoDocumentoAtividade;
  descricao?: string;
  nome_original: string;
  data_documento: string;
};

export async function listDocuments(
  atividadeId: string,
  signal?: AbortSignal,
): Promise<EvidenceDocument[]> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/documentos/`,
    { signal },
  );
  return res.json();
}

export async function requestDocumentUploadUrl(
  atividadeId: string,
  payload: DocumentUploadUrlPayload,
): Promise<UploadUrlResponse> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/documentos/upload-url/`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return res.json();
}

export async function confirmDocument(
  atividadeId: string,
  payload: DocumentConfirmPayload,
): Promise<EvidenceDocument> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/documentos/confirm/`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return res.json();
}

export async function deleteDocument(
  atividadeId: string,
  docId: number,
): Promise<void> {
  await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/documentos/${docId}/`,
    { method: "DELETE" },
  );
}

/**
 * Atualiza campos editáveis inline do documento (tipo e descrição). Depende do
 * BE expor PATCH /documentos/{id}/ — mesma nota do updatePhoto.
 */
export async function updateDocument(
  atividadeId: string,
  docId: number,
  patch: Partial<Pick<EvidenceDocument, "tipo" | "descricao">>,
): Promise<EvidenceDocument> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/documentos/${docId}/`,
    { method: "PATCH", body: JSON.stringify(patch) },
  );
  return res.json();
}

/** Retorna a URL pré-assinada para download; a UI abre em nova aba. */
export async function getDocumentDownloadUrl(
  atividadeId: string,
  docId: number,
): Promise<string> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/${atividadeId}/documentos/${docId}/download/`,
  );
  const data = (await res.json()) as { url: string; expires_in: number };
  return data.url;
}
