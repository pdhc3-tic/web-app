import { formatDistanceToNowStrict, format } from "date-fns";
import { ptBR } from "date-fns/locale";

/**
 * Tempo relativo em pt-BR (ex.: "há 3 dias", "há 2 horas") via date-fns.
 * Retorna string vazia quando a data é nula/inválida — cabe ao chamador
 * decidir o texto de fallback (ex.: "Nunca acessou").
 */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";

  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";

  return formatDistanceToNowStrict(date, { addSuffix: true, locale: ptBR });
}

/** Data absoluta legível para tooltip (ex.: "18/06/2026 14:30"). */
export function absoluteDateTime(
  iso: string | null | undefined,
): string | undefined {
  if (!iso) return undefined;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return undefined;
  return format(date, "dd/MM/yyyy HH:mm", { locale: ptBR });
}
