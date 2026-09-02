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

/** Grade de 6×7 iniciada no domingo — padrão brasileiro. */
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

      <div className="grid grid-cols-7 auto-rows-fr">
        {dias.map((dia) => {
          const key = format(dia, "yyyy-MM-dd");
          const doMes = isSameMonth(dia, anchor);
          const hoje = isToday(dia);
          const eventosDoDia = eventosPorDia[key] ?? [];
          const excedente = eventosDoDia.length - MAX_EVENTS_PER_CELL;

          return (
            <button
              type="button"
              key={key}
              onClick={() => onCreateAt(dia)}
              aria-label={`Criar atividade em ${format(dia, "dd 'de' MMMM 'de' yyyy", { locale: ptBR })}`}
              className={`group relative flex min-h-24 flex-col gap-1 border-b border-r border-border p-1.5 text-left transition-colors hover:bg-surface-warm/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                doMes ? "bg-surface" : "bg-surface-muted/40"
              }`}
            >
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
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectEvent(ev);
                  }}
                />
              ))}

              {excedente > 0 && (
                <span className="mt-auto self-start text-2xs font-medium text-text-muted">
                  +{excedente} mais
                </span>
              )}
            </button>
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
};

export function EventPill({ event, onClick, compact }: PillProps) {
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
      className={`flex items-center gap-1 overflow-hidden rounded border border-border ${bgClass} px-1 py-0.5 text-left text-2xs text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary`}
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
