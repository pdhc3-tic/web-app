"use client";

import { useMemo } from "react";
import {
  addDays,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  isToday,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { ptBR } from "date-fns/locale";
import type { CalendarActivityEvent } from "@/app/lib/atividadesCalendario";
import { formatTime, parseDayStart } from "@/app/lib/datetime";

type Props = {
  /** Data qualquer dentro do mês exibido. */
  anchor: Date;
  events: CalendarActivityEvent[];
  onSelectEvent: (event: CalendarActivityEvent) => void;
  onCreateAt: (date: Date) => void;
};

const WEEKDAY_LABELS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const MAX_EVENTS_PER_CELL = 3;

/**
 * Grade mensal iniciada no domingo — padrão brasileiro.
 *
 * O número de linhas VARIA: a grade vai de `startOfWeek(início do mês)` a
 * `endOfWeek(fim do mês)`, o que dá 4 a 6 semanas conforme onde o mês cai
 * (setembro/2026, por exemplo, rende 5 linhas / 35 células). Sempre semanas
 * completas, nunca 6 fixas.
 */
export function MonthView({ anchor, events, onSelectEvent, onCreateAt }: Props) {
  const dias = useMemo(() => {
    const gridStart = startOfWeek(startOfMonth(anchor), { weekStartsOn: 0 });
    const gridEnd = endOfWeek(endOfMonth(anchor), { weekStartsOn: 0 });
    const out: Date[] = [];
    for (let d = gridStart; d <= gridEnd; d = addDays(d, 1)) out.push(d);
    return out;
  }, [anchor]);

  const eventosPorDia = useMemo(
    () => groupEventsByDate(events, dias),
    [events, dias],
  );

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface">
      <div className="grid grid-cols-7 border-b border-border bg-surface-muted text-2xs font-semibold uppercase tracking-wide text-text-muted">
        {WEEKDAY_LABELS.map((wd) => (
          <div key={wd} className="px-2 py-2 text-center">
            {wd}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 auto-rows-fr" data-testid="calendario-grade-mes">
        {dias.map((dia) => {
          const key = format(dia, "yyyy-MM-dd");
          const doMes = isSameMonth(dia, anchor);
          const hoje = isToday(dia);
          const eventosDoDia = eventosPorDia[key] ?? [];
          const excedente = eventosDoDia.length - MAX_EVENTS_PER_CELL;

          return (
            <div
              key={key}
              data-testid={`calendario-dia-${key}`}
              className={`relative flex min-h-24 flex-col border-b border-r border-border transition-colors hover:bg-surface-warm/40 ${
                doMes ? "bg-surface" : "bg-surface-muted/40"
              }`}
            >
              {/* Alvo de "criar neste dia": uma camada de fundo, e não a célula
                  inteira. A célula era um <button> com as pílulas de evento —
                  outros <button> — dentro dele, o que é HTML inválido e
                  quebrava a hidratação ("<button> cannot be a descendant of
                  <button>"). Aqui os dois cliques ficam em elementos irmãos.

                  O outline entra com offset NEGATIVO porque este botão cobre a
                  célula inteira: um anel para fora seria cortado pelo
                  `overflow-hidden` da grade. */}
              <button
                type="button"
                onClick={() => onCreateAt(dia)}
                aria-label={`Criar atividade em ${format(dia, "dd 'de' MMMM 'de' yyyy", { locale: ptBR })}`}
                data-testid={`calendario-criar-${key}`}
                className="absolute inset-0 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary"
              />

              {/* `pointer-events-none` deixa o clique no vazio e no número do
                  dia atravessar para o botão de fundo; as pílulas reativam o
                  ponteiro para si. */}
              <div className="pointer-events-none relative flex flex-1 flex-col gap-1 p-1.5">
                <span
                  className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                    hoje
                      ? "bg-primary text-surface"
                      : doMes
                        ? "text-text"
                        : "text-text-muted"
                  }`}
                >
                  {format(dia, "d")}
                </span>

                {eventosDoDia.slice(0, MAX_EVENTS_PER_CELL).map((ev) => (
                  <EventPill
                    key={`${key}-${ev.id}`}
                    event={ev}
                    compact
                    className="pointer-events-auto"
                    // Sem stopPropagation: o botão de fundo é IRMÃO desta
                    // pílula, não ancestral, então o clique não chega nele.
                    onClick={() => onSelectEvent(ev)}
                  />
                ))}

                {excedente > 0 && (
                  <span className="mt-auto self-start text-2xs font-medium text-text-muted">
                    +{excedente} mais
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Um evento pode cobrir vários dias — retorna um índice { yyyy-MM-dd → [] }
 * cobrindo todo o intervalo dentro da grade visível.
 */
function groupEventsByDate(
  events: CalendarActivityEvent[],
  visibleDays: Date[],
): Record<string, CalendarActivityEvent[]> {
  const map: Record<string, CalendarActivityEvent[]> = {};
  for (const d of visibleDays) map[format(d, "yyyy-MM-dd")] = [];

  for (const ev of events) {
    const inicio = parseDayStart(ev.data_inicio);
    const fim = parseDayStart(ev.data_fim);
    if (!inicio || !fim) continue;
    for (const d of visibleDays) {
      if (d >= inicio && d <= fim) {
        map[format(d, "yyyy-MM-dd")].push(ev);
      }
    }
  }
  return map;
}

// ── Reutilizado pelas outras views ──────────────────────────────────────────

type PillProps = {
  event: CalendarActivityEvent;
  onClick: (e: React.MouseEvent) => void;
  compact?: boolean;
  /** Classes extras — a grade do mês usa para reativar o ponteiro na pílula. */
  className?: string;
};

export function EventPill({ event, onClick, compact, className }: PillProps) {
  const horaInicio = formatTime(event.data_inicio);
  const bgClass = compact
    ? "bg-surface hover:bg-surface-muted/60"
    : "bg-surface hover:bg-surface-muted/60";
  return (
    <button
      type="button"
      onClick={onClick}
      title={
        horaInicio
          ? `${horaInicio} · ${event.titulo} · ${event.status_display}`
          : `${event.titulo} · ${event.status_display}`
      }
      data-testid={`calendario-evento-${event.id}`}
      className={`flex items-center gap-1 overflow-hidden rounded border border-border ${bgClass} px-1 py-0.5 text-left text-2xs text-text focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary ${
        className ?? ""
      }`}
      style={{ borderLeft: `3px solid ${event.cor}` }}
    >
      {event.atrasada && (
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-error-text"
          aria-label="Atrasada"
        />
      )}
      {horaInicio && (
        <span className="shrink-0 font-medium tabular-nums text-text-muted">
          {horaInicio}
        </span>
      )}
      <span className="truncate">{event.titulo}</span>
    </button>
  );
}

export { parseDayStart };
