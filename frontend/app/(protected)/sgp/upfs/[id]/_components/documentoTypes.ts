export const TIPO_DOC_OPTIONS = [
  { value: "dap_caf", label: "DAP/CAF" },
  { value: "contrato", label: "Contrato" },
  { value: "laudo", label: "Laudo" },
  { value: "identidade", label: "Identidade" },
  { value: "outro", label: "Outro" },
] as const;

export type TipoDocumento = (typeof TIPO_DOC_OPTIONS)[number]["value"];

export const ACCEPTED_CONTENT_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
] as const;

export type ContentType = (typeof ACCEPTED_CONTENT_TYPES)[number];

export const MAX_DOC_SIZE_BYTES = 10 * 1024 * 1024;

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

export type DocumentoWritePayload = {
  tipo: TipoDocumento;
  descricao: string;
  data_documento: string;
  nome_original: string;
  content_type: string;
  tamanho_bytes: number;
};

export function tipoDocumentoLabel(tipo: string): string {
  return TIPO_DOC_OPTIONS.find((o) => o.value === tipo)?.label ?? tipo;
}
