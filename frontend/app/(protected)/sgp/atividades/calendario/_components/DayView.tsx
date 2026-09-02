"use client";

import { useMemo } from "react";
import { differenceInCalendarDays, format, isToday } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarPlus, Clock, MapPin, User } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import type { CalendarActivityEvent } from "@/app/lib/atividadesCalendario";
import { formatTimeRange, parseDayStart } from "@/app/lib/datetime";

type Props = {
  anchor: Date;
  events: CalendarActivityEvent[];
  onSelectEvent: (event: CalendarActivityEvent) => void;
  onCreateAt: (date: Date) => void;
};

/** Lista vertical dos eventos do dia com contexto (município, técnico). */
export function DayView({ anchor, events, onSelectEvent, onCreateAt }: Props) {
  const doDia = useMemo(() => {
    const y = anchor.getFullYear();
    const m = anchor.getMonth();
    const d = anchor.getDate();
    const target = new Date(y, m, d);
    return events
      .filter((ev) => {
        const inicio = parseDayStart(ev.data_inicio);
        const fim = parseDayStart(ev.data_fim);
        if (!inicio || !fim) return false;
        return target >= inicio && target <= fim;
      })
      .sort((a, b) => a.data_inicio.localeCompare(b.data_inicio));
  }, [anchor, events]);

  const hoje = isToday(anchor);

  return (
    <div className="flex flex-col gap-4">
      <header
        className={`flex items-center justify-between rounded-lg border border-border bg-surface p-4 ${
          hoje ? "border-primary/60" : ""
        }`}
      >
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-text-muted">
            {format(anchor, "EEEE", { locale: ptBR })}
          </p>
          <h3 className="text-xl font-semibold text-text">
            {format(anchor, "dd 'de' MMMM 'de' yyyy", { locale: ptBR })}
          </h3>
          <p className="mt-1 text-xs text-text-muted">
            {doDia.length === 0
              ? "Nenhuma atividade agendada."
              : `${doDia.length} atividade${doDia.length === 1 ? "" : "s"} neste dia.`}
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          leftIcon={<CalendarPlus className="h-4 w-4" />}
          onClick={() => onCreateAt(anchor)}
        >
          Nova atividade
        </Button>
      </header>

      {doDia.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState
            icon={<CalendarPlus className="h-7 w-7" />}
            title="Dia livre"
            description="Nenhuma atividade planejada. Aproveite para agendar uma."
            action={
              <Button
                leftIcon={<CalendarPlus className="h-4 w-4" />}
                onClick={() => onCreateAt(anchor)}
              >
                Criar atividade neste dia
              </Button>
            }
          />
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {doDia.map((ev) => (
            <li key={ev.id}>
              <DayCard
                event={ev}
                anchor={anchor}
                onClick={() => onSelectEvent(ev)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DayCard({
  event,
  anchor,
  onClick,
}: {
  event: CalendarActivityEvent;
  anchor: Date;
  onClick: () => void;
}) {
  const inicio = parseDayStart(event.data_inicio);
  const fim = parseDayStart(event.data_fim);
  const totalDias =
    inicio && fim ? differenceInCalendarDays(fim, inicio) + 1 : 1;
  const diaAtual = inicio ? differenceInCalendarDays(anchor, inicio) + 1 : 1;
  const multiplo = totalDias > 1;
  const horario = formatTimeRange(event.data_inicio, event.data_fim);

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-start gap-3 rounded-lg border border-border bg-surface p-4 text-left transition hover:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      style={{ borderLeftWidth: 4, borderLeftColor: event.cor }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-semibold text-white"
            style={{ backgroundColor: event.cor }}
          >
            {event.status_display}
          </span>
          <span className="text-2xs uppercase tracking-wide text-text-muted">
            {event.tipo_atividade_display}
          </span>
          {horario && (
            <span className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2 py-0.5 text-2xs font-medium tabular-nums text-text">
              <Clock className="h-3 w-3" aria-hidden="true" />
              {horario}
            </span>
          )}
          {event.atrasada && (
            <span className="rounded-full bg-error-bg px-2 py-0.5 text-2xs font-semibold text-error-text">
              Atrasada
            </span>
          )}
          {multiplo && (
            <span className="rounded-full bg-surface-muted px-2 py-0.5 text-2xs text-text-muted">
              Dia {diaAtual} de {totalDias}
            </span>
          )}
        </div>
        <h4 className="mt-2 truncate text-base font-medium text-text group-hover:text-primary">
          {event.titulo}
        </h4>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
          <span className="inline-flex items-center gap-1">
            <User className="h-3.5 w-3.5" aria-hidden="true" />
            {event.tecnico_responsavel.nome}
          </span>
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
            {event.municipio.nome}
            {event.comunidade && ` · ${event.comunidade.nome}`}
          </span>
        </p>
      </div>
    </button>
  );
}
