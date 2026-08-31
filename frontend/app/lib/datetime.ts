import { formatDistanceToNowStrict, format, startOfDay } from "date-fns";
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

/**
 * Converte uma data do backend para `Date` no fuso LOCAL.
 *
 * Datas puras "YYYY-MM-DD" são interpretadas como UTC por `new Date()` e podem
 * deslocar um dia no fuso local; monta-se a partir dos componentes para evitar
 * isso. Devolve `null` para nulo/inválido.
 */
export function parseDateOnly(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Data (sem hora) no formato DD/MM/YYYY. Retorna "" para nulo/inválido. */
export function formatDate(iso: string | null | undefined): string {
  const date = parseDateOnly(iso);
  if (!date) return "";
  return format(date, "dd/MM/yyyy", { locale: ptBR });
}

/**
 * Início do dia LOCAL de uma data do backend, para agrupamento por dia.
 *
 * `Activity.data_inicio`/`data_fim` são DateTimeField e chegam como ISO com
 * fuso ("2026-08-02T13:00:00-03:00"). O calendário posiciona eventos em células
 * de dia, então comparar contra a data crua deixaria o próprio dia de início de
 * fora (meia-noite < 13:00). Truncar no início do dia resolve, e continua
 * aceitando datas puras "YYYY-MM-DD".
 */
export function parseDayStart(iso: string | null | undefined): Date | null {
  const date = parseDateOnly(iso);
  return date ? startOfDay(date) : null;
}

/**
 * Hora local no formato HH:mm. Devolve "" quando a data é pura (sem horário),
 * nula ou inválida — o chamador simplesmente não exibe nada nesse caso.
 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return format(date, "HH:mm", { locale: ptBR });
}

/** Faixa "HH:mm – HH:mm" (ou só o início, quando fim é igual/ausente). */
export function formatTimeRange(
  inicio: string | null | undefined,
  fim: string | null | undefined,
): string {
  const hi = formatTime(inicio);
  const hf = formatTime(fim);
  if (!hi) return "";
  return hf && hf !== hi ? `${hi} – ${hf}` : hi;
}

/**
 * Início do dia LOCAL como ISO em UTC, para filtros de range no backend.
 *
 * Entrada: "YYYY-MM-DD" do `<input type="date">` (sempre local). Saída: ISO
 * UTC que representa 00:00 do fuso do navegador. Concatenar `T00:00:00Z`
 * cru interpretaria a data como UTC e deslocaria a janela em horas (o dia
 * "28/08" no BR começa às 03:00Z, não 00:00Z), escondendo eventos das
 * primeiras horas locais e incluindo eventos do dia anterior.
 *
 * Devolve `undefined` para entrada vazia/inválida.
 */
export function localDayStartISO(ymd: string | null | undefined): string | undefined {
  const parsed = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd ?? "");
  if (!parsed) return undefined;
  const date = new Date(
    Number(parsed[1]),
    Number(parsed[2]) - 1,
    Number(parsed[3]),
    0, 0, 0, 0,
  );
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/**
 * Fim do dia LOCAL (23:59:59.999) como ISO em UTC. Complemento de
 * `localDayStartISO` — ver docstring dele para o motivo.
 */
export function localDayEndISO(ymd: string | null | undefined): string | undefined {
  const parsed = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd ?? "");
  if (!parsed) return undefined;
  const date = new Date(
    Number(parsed[1]),
    Number(parsed[2]) - 1,
    Number(parsed[3]),
    23, 59, 59, 999,
  );
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}
