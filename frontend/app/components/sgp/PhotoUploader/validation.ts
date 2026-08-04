const DEFAULT_MAX_SIZE_MB = 5;
export const DEFAULT_ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

export type FileValidationResult =
  | { valid: true }
  | { valid: false; message: string };

/** Valida tipo e tamanho no cliente, espelhando as regras do backend (upf_foto.py). */
export function validateFile(
  file: File,
  maxSizeMB: number = DEFAULT_MAX_SIZE_MB,
  acceptedTypes: string[] = DEFAULT_ACCEPTED_TYPES,
): FileValidationResult {
  if (!acceptedTypes.includes(file.type)) {
    return {
      valid: false,
      message: "Tipo de arquivo inválido. Envie JPEG, PNG ou WEBP.",
    };
  }

  const maxBytes = maxSizeMB * 1024 * 1024;
  if (file.size > maxBytes) {
    return {
      valid: false,
      message: `Arquivo excede o tamanho máximo de ${maxSizeMB} MB.`,
    };
  }

  return { valid: true };
}
