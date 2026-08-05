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

/** Valida foto (JPEG/PNG/WEBP, até 800 KB). */
export function validatePhoto(file: File): FileValidationResult {
  if (!(PHOTO_ACCEPTED_TYPES as readonly string[]).includes(file.type)) {
    return {
      valid: false,
      message: `${file.name}: formato inválido. Envie JPEG, PNG ou WEBP.`,
    };
  }
  if (file.size > PHOTO_MAX_SIZE_BYTES) {
    return {
      valid: false,
      message: `${file.name}: excede ${formatBytes(PHOTO_MAX_SIZE_BYTES)}. Comprima antes de enviar.`,
    };
  }
  return { valid: true };
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
