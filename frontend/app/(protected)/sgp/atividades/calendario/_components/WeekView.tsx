"use client";

import { useMemo } from "react";
import {
  addDays,
  endOfWeek,
  format,
  isToday,
  startOfWeek,
} from "date-fns";
import { ptBR } from "date-fns/locale";
import { Plus } from "lucide-react";
import type { CalendarActivityEvent } from "@/app/lib/atividadesCalendario";
import { EventPill } from "./MonthView";
import { parseDayStart } from "@/app/lib/datetime";

type Props = {
  anchor: Date;
  events: CalendarActivityEvent[];
  onSelectEvent: (event: CalendarActivityEvent) => void;
  onCreateAt: (date: Date) => void;
};

/** 7 colunas (domingo → sábado). Cada coluna lista os eventos do dia. */
export function WeekView({ anchor, events, onSelectEvent, onCreateAt }: Props) {
  const dias = useMemo(() => {
    const start = startOfWeek(anchor, { weekStartsOn: 0 });
    const end = endOfWeek(anchor, { weekStartsOn: 0 });
    const out: Date[] = [];
    for (let d = start; d <= end; d = addDays(d, 1)) out.push(d);
    return out;
  }, [anchor]);

  const eventosPorDia = useMemo(() => {
    const map: Record<string, CalendarActivityEvent[]> = {};
    for (const d of dias) map[format(d, "yyyy-MM-dd")] = [];
    for (const ev of events) {
      const inicio = parseDayStart(ev.data_inicio);
      const fim = parseDayStart(ev.data_fim);
      if (!inicio || !fim) continue;
      for (const d of dias) {
        if (d >= inicio && d <= fim) {
          map[format(d, "yyyy-MM-dd")].push(ev);
        }
      }
    }
    return map;
  }, [events, dias]);

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-7 md:gap-2">
      {dias.map((dia) => {
        const key = format(dia, "yyyy-MM-dd");
        const eventosDoDia = eventosPorDia[key] ?? [];
        const hoje = isToday(dia);
        return (
          <section
            key={key}
            className="flex min-h-40 flex-col overflow-hidden rounded-lg border border-border bg-surface"
          >
            <header
              className={`flex items-center justify-between border-b border-border px-3 py-2 ${
                hoje ? "bg-primary/10 text-primary" : "bg-surface-muted"
              }`}
            >
              <div className="flex flex-col leading-tight">
                <span className="text-2xs font-semibold uppercase tracking-wide text-text-muted">
                  {format(dia, "EEE", { locale: ptBR })}
                </span>
                <span
                  className={`text-lg font-semibold ${hoje ? "text-primary" : "text-text"}`}
                >
                  {format(dia, "d")}
                </span>
              </div>
              <button
                type="button"
                onClick={() => onCreateAt(dia)}
                title="Nova atividade neste dia"
                aria-label={`Nova atividade em ${format(dia, "dd/MM", { locale: ptBR })}`}
                className="inline-flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-surface hover:text-primary"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </header>

            <div className="flex flex-1 flex-col gap-1 p-2">
              {eventosDoDia.length === 0 ? (
                <button
                  type="button"
                  onClick={() => onCreateAt(dia)}
                  className="mt-1 text-left text-2xs text-text-muted italic hover:text-text"
                >
                  Sem atividades
                </button>
              ) : (
                eventosDoDia.map((ev) => (
                  <EventPill
                    key={`${key}-${ev.id}`}
                    event={ev}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectEvent(ev);
                    }}
                  />
                ))
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
