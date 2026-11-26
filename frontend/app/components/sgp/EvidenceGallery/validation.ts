/**
 * Validação client-side dos arquivos de evidência — espelha as regras dos
 * serializers do backend (BE-2) para evitar ida-e-volta desnecessária.
 */
import {
  DOCUMENT_ACCEPTED_TYPES,
  DOCUMENT_MAX_SIZE_BYTES,
  PHOTO_ACCEPTED_TYPES,
  PHOTO_MAX_SIZE_BYTES,
  formatBytes,
} from "./types";

export type FileValidationResult =
  | { valid: true }
  | { valid: false; message: string };

/**
 * Valida o formato da foto (JPEG/PNG/WEBP). O tamanho não recusa aqui: acima
 * de 800 KB a foto é comprimida antes do envio (`compressao.ts`, #464).
 */
export function validatePhoto(file: File): FileValidationResult {
  if (!(PHOTO_ACCEPTED_TYPES as readonly string[]).includes(file.type)) {
    return {
      valid: false,
      message: `${file.name}: formato inválido. Envie JPEG, PNG ou WEBP.`,
    };
  }
  return { valid: true };
}

/** Mensagem para a foto que a compressão não conseguiu deixar dentro do limite. */
export function mensagemFalhaCompressao(nome: string, motivo: "ilegivel" | "grande_demais"): string {
  return motivo === "ilegivel"
    ? `${nome}: não foi possível ler a imagem para comprimir. Tente outra foto.`
    : `${nome}: mesmo comprimida, a foto passa de ${formatBytes(PHOTO_MAX_SIZE_BYTES)}. Tente outra foto.`;
}

/** Valida documento (apenas PDF, até 10 MB). */
export function validateDocument(file: File): FileValidationResult {
  if (!(DOCUMENT_ACCEPTED_TYPES as readonly string[]).includes(file.type)) {
    return {
      valid: false,
      message: `${file.name}: formato inválido. Apenas PDF é aceito.`,
    };
  }
  if (file.size > DOCUMENT_MAX_SIZE_BYTES) {
    return {
      valid: false,
      message: `${file.name}: excede ${formatBytes(DOCUMENT_MAX_SIZE_BYTES)}.`,
    };
  }
  return { valid: true };
}
