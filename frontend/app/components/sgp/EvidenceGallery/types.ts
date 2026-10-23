/**
 * Tipos e constantes do EvidenceGallery. Espelham os serializers do backend em
 * apps/sgp/views/activity_foto.py e apps/sgp/views/activity_documentos.py.
 */

// ── Fotos ────────────────────────────────────────────────────────────────────

export const PHOTO_ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const PHOTO_MAX_SIZE_BYTES = 819_200; // 800 KB (MAX_PHOTO_SIZE_BYTES)
export const MAX_PHOTOS_PER_ACTIVITY = 10;

export type PhotoContentType = (typeof PHOTO_ACCEPTED_TYPES)[number];

export type EvidencePhoto = {
  id: number;
  activity: number;
  arquivo_url: string;
  legenda: string;
  data_hora_captura: string | null;
  latitude: string | null;
  longitude: string | null;
  ordem: number;
  content_type: string;
  tamanho_bytes: number;
  ativo: boolean;
  criado_em: string;
  /**
   * Marcado true quando o registro chegou por sincronização do SCA mas ainda
   * não foi confirmado pelo backend. O backend atual não seta essa flag; ela
   * ficará em uso quando a integração SCA (issues 156-160) estiver pronta.
   */
  pendente_sincronizacao?: boolean;
};

// ── Documentos ───────────────────────────────────────────────────────────────

export const DOCUMENT_ACCEPTED_TYPES = ["application/pdf"] as const;
export const DOCUMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
export const MAX_DOCUMENTS_PER_ACTIVITY = 5;

export type DocumentContentType = (typeof DOCUMENT_ACCEPTED_TYPES)[number];

// A lista e os rótulos dos tipos vêm de `useSgpChoices().atividade_documento_tipo` (#272).
export type TipoDocumentoAtividade =
  | "lista_presenca"
  | "ata"
  | "relatorio_parcial"
  | "declaracao"
  | "contrato"
  | "outro";

export type EvidenceDocument = {
  id: number;
  activity: number;
  tipo: TipoDocumentoAtividade;
  tipo_display: string;
  descricao: string;
  nome_original: string;
  content_type: string;
  tamanho_bytes: number;
  data_documento: string;
  ativo: boolean;
  criado_em: string;
  pendente_sincronizacao?: boolean;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
