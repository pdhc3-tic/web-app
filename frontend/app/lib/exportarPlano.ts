/**
 * Utilitários comuns às exportações de arquivo do SGP: o formato, o nome que
 * vem no `Content-Disposition` e o download da blob. O Plano de Trabalho e as
 * Atividades são gerados em segundo plano (`app/lib/exportacoes.ts`).
 */

export type FormatoExport = "csv" | "xlsx";

export const FORMATO_OPTIONS = [
  { value: "csv", label: "CSV (.csv)" },
  { value: "xlsx", label: "Excel (.xlsx)" },
];

/** A resposta síncrona estourou o teto de espera — a UI mostra uma mensagem própria. */
export class ExportTimeoutError extends Error {
  constructor() {
    super("A geração do arquivo excedeu o tempo limite.");
    this.name = "ExportTimeoutError";
  }
}

/**
 * Lê o nome do arquivo do `Content-Disposition`, que o backend expõe via CORS.
 * Devolve `null` quando o header não veio, e quem chama decide o nome padrão.
 */
export function nomeDoContentDisposition(header: string | null): string | null {
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

/** Entrega o blob ao browser por um <a download> descartável. */
export function dispararDownload(blob: Blob, nome: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revogar no mesmo tick cancela a gravação em alguns browsers — o download
  // ainda não começou quando o click retorna.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
