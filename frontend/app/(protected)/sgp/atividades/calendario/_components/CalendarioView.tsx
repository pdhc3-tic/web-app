"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  addDays,
  addMonths,
  addWeeks,
  differenceInCalendarDays,
  endOfMonth,
  endOfWeek,
  format,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  AlertTriangle,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
} from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  listCalendarActivities,
  type CalendarActivityEvent,
} from "@/app/lib/atividadesCalendario";
import { listAcoes, listTecnicos, type AcaoPT } from "@/app/lib/atividades";
import { fetchProjetoOptions } from "@/app/lib/upfs";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import {
  CalendarFilters,
  EMPTY_CALENDAR_FILTERS,
  type CalendarFiltersValue,
} from "./CalendarFilters";
import { DayView } from "./DayView";
import { WeekView } from "./WeekView";
import { MonthView } from "./MonthView";
import { EventoDetailsSlideOver } from "./EventoDetailsSlideOver";
import { STATUS_HEX_COLORS } from "./statusColor";

export type ViewMode = "dia" | "semana" | "mes";

const VIEW_MODES: { value: ViewMode; label: string }[] = [
  { value: "dia", label: "Dia" },
  { value: "semana", label: "Semana" },
  { value: "mes", label: "Mês" },
];

function parseAnchor(param: string | null): Date {
  if (param) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(param);
    if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function toIsoDate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

/** Intervalo consultado ao backend para cada modo de visualização. */
function computeRange(view: ViewMode, anchor: Date): { inicio: Date; fim: Date } {
  if (view === "dia") return { inicio: anchor, fim: anchor };
  if (view === "semana") {
    return {
      inicio: startOfWeek(anchor, { weekStartsOn: 0 }),
      fim: endOfWeek(anchor, { weekStartsOn: 0 }),
    };
  }
  // Mês → grade do dom → sáb cobrindo a primeira e a última semana visíveis.
  return {
    inicio: startOfWeek(startOfMonth(anchor), { weekStartsOn: 0 }),
    fim: endOfWeek(endOfMonth(anchor), { weekStartsOn: 0 }),
  };
}

export function CalendarioView() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const choices = useSgpChoices();

  const [view, setView] = useState<ViewMode>(() => {
    const v = searchParams.get("view");
    return v === "dia" || v === "semana" || v === "mes" ? v : "mes";
  });
  const [anchor, setAnchor] = useState<Date>(() =>
    parseAnchor(searchParams.get("data")),
  );
  const [filters, setFilters] = useState<CalendarFiltersValue>(() => ({
    acao: searchParams.get("acao") ?? "",
    projeto: searchParams.get("projeto") ?? "",
    tecnico: searchParams.get("tecnico") ?? "",
    tipo: searchParams.get("tipo") ?? "",
    status: searchParams.get("status") ?? "",
  }));

  const [events, setEvents] = useState<CalendarActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [acoes, setAcoes] = useState<AcaoPT[]>([]);
  const [projetoOptions, setProjetoOptions] = useState<SelectOption[]>([]);
  const [tecnicoOptions, setTecnicoOptions] = useState<SelectOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);

  const [selected, setSelected] = useState<CalendarActivityEvent | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some((v) => v !== ""),
    [filters],
  );

  const range = useMemo(() => computeRange(view, anchor), [view, anchor]);
  // 90 dias é o teto do endpoint; a checagem fora do effect evita setState
  // encadeada e permite exibir o aviso sem disparar fetch inútil.
  const foraDoIntervalo = useMemo(
    () => differenceInCalendarDays(range.fim, range.inicio) + 1 > 90,
    [range],
  );

  // ── Sincroniza estado com URL ────────────────────────────────────────────
  useEffect(() => {
    const qs = new URLSearchParams();
    if (view !== "mes") qs.set("view", view);
    qs.set("data", toIsoDate(anchor));
    if (filters.acao) qs.set("acao", filters.acao);
    if (filters.projeto) qs.set("projeto", filters.projeto);
    if (filters.tecnico) qs.set("tecnico", filters.tecnico);
    if (filters.tipo) qs.set("tipo", filters.tipo);
    if (filters.status) qs.set("status", filters.status);
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [view, anchor, filters, pathname, router]);

  // ── Opções dos filtros ────────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOptionsLoading(true);
    Promise.all([
      listAcoes(controller.signal).catch(() => [] as AcaoPT[]),
      fetchProjetoOptions(controller.signal),
      listTecnicos(controller.signal),
    ])
      .then(([acoesData, projetos, tecnicos]) => {
        if (controller.signal.aborted) return;
        setAcoes(acoesData);
        setProjetoOptions(projetos);
        setTecnicoOptions(
          tecnicos.map((t) => ({ value: String(t.id), label: t.nome })),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setOptionsLoading(false);
      });
    return () => controller.abort();
  }, []);

  // ── Consulta ao backend ───────────────────────────────────────────────────
  useEffect(() => {
    if (foraDoIntervalo) return; // aviso exibido no render; nada a buscar.
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    listCalendarActivities(
      {
        inicio: toIsoDate(range.inicio),
        fim: toIsoDate(range.fim),
        acao: filters.acao || undefined,
        projeto: filters.projeto || undefined,
        tecnico: filters.tecnico || undefined,
        tipo: filters.tipo || undefined,
        status: filters.status || undefined,
      },
      controller.signal,
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        setEvents(data.results);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as atividades do período.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [foraDoIntervalo, range.inicio, range.fim, filters, reloadKey]);

  const acaoSelecionada = useMemo(
    () => acoes.find((a) => String(a.id) === filters.acao) ?? null,
    [acoes, filters.acao],
  );

  // ── Navegação temporal ────────────────────────────────────────────────────
  function irParaHoje() {
    const now = new Date();
    setAnchor(new Date(now.getFullYear(), now.getMonth(), now.getDate()));
  }

  function avancar(dir: 1 | -1) {
    if (view === "dia") setAnchor((d) => addDays(d, dir));
    else if (view === "semana") setAnchor((d) => addWeeks(d, dir));
    else setAnchor((d) => addMonths(d, dir));
  }

  const patchFilters = useCallback(
    (patch: Partial<CalendarFiltersValue>) => {
      setFilters((prev) => ({ ...prev, ...patch }));
    },
    [],
  );

  function limparFiltros() {
    setFilters(EMPTY_CALENDAR_FILTERS);
  }

  // ── Handlers das views ───────────────────────────────────────────────────
  const handleSelectEvent = useCallback((event: CalendarActivityEvent) => {
    setSelected(event);
    setDetailOpen(true);
  }, []);

  const handleCreateAt = useCallback(
    (date: Date) => {
      const iso = toIsoDate(date);
      const qs = new URLSearchParams();
      qs.set("data_inicio", iso);
      qs.set("data_fim", iso);
      if (filters.tecnico) qs.set("tecnico_responsavel", filters.tecnico);
      router.push(`/sgp/atividades/nova/?${qs.toString()}`);
    },
    [filters.tecnico, router],
  );

  // Rótulo do período (formato pt-BR) — muda por view.
  const periodoLabel = useMemo(() => {
    if (view === "dia") {
      return format(anchor, "dd 'de' MMMM 'de' yyyy", { locale: ptBR });
    }
    if (view === "semana") {
      const ini = startOfWeek(anchor, { weekStartsOn: 0 });
      const fim = endOfWeek(anchor, { weekStartsOn: 0 });
      return `${format(ini, "dd/MM")} — ${format(fim, "dd/MM 'de' yyyy", { locale: ptBR })}`;
    }
    return format(anchor, "MMMM 'de' yyyy", { locale: ptBR });
  }, [view, anchor]);

  return (
    <>
      <PageHeader>
        <div className="flex w-full items-center justify-between gap-3">
          <h1 className="truncate text-base font-semibold text-text">
            Calendário
          </h1>
          <Button
            size="sm"
            onClick={() => handleCreateAt(anchor)}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Nova atividade
          </Button>
        </div>
      </PageHeader>

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Atividades", href: "/sgp/atividades" },
            { label: "Calendário" },
          ]}
        />

        {/* Cabeçalho de navegação */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3">
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={irParaHoje}>
              Hoje
            </Button>
            <div className="inline-flex items-center rounded-md border border-border">
              <button
                type="button"
                onClick={() => avancar(-1)}
                aria-label="Período anterior"
                className="inline-flex h-8 w-8 items-center justify-center text-text-muted hover:bg-surface-muted hover:text-text"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => avancar(1)}
                aria-label="Próximo período"
                className="inline-flex h-8 w-8 items-center justify-center border-l border-border text-text-muted hover:bg-surface-muted hover:text-text"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <p className="ml-2 text-sm font-medium capitalize text-text">
              {periodoLabel}
            </p>
          </div>

          <ViewSwitcher value={view} onChange={setView} />
        </div>

        <CalendarFilters
          value={filters}
          onChange={patchFilters}
          onClear={limparFiltros}
          hasActiveFilters={hasActiveFilters}
          acoes={acoes}
          acaoSelecionada={acaoSelecionada}
          choices={choices}
          projetoOptions={projetoOptions}
          tecnicoOptions={tecnicoOptions}
          optionsLoading={optionsLoading}
        />

        {foraDoIntervalo && (
          <div className="flex items-start gap-2 rounded-md border border-warning-text bg-warning-bg px-4 py-3 text-sm text-warning-text">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Intervalo maior que 90 dias — reduza a janela ou troque de
              visualização.
            </span>
          </div>
        )}

        {!foraDoIntervalo && loading && (
          <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-4 py-3 text-sm text-text-muted">
            <Spinner className="h-4 w-4 animate-spin" />
            Carregando atividades…
          </div>
        )}

        {!foraDoIntervalo && error && !loading && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface px-6 py-10 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-5 w-5" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)}>
              Tentar novamente
            </Button>
          </div>
        )}

        {!foraDoIntervalo && !error && !loading && (
          <>
            {view === "dia" && (
              <DayView
                anchor={anchor}
                events={events}
                onSelectEvent={handleSelectEvent}
                onCreateAt={handleCreateAt}
              />
            )}
            {view === "semana" && (
              <WeekView
                anchor={anchor}
                events={events}
                onSelectEvent={handleSelectEvent}
                onCreateAt={handleCreateAt}
              />
            )}
            {view === "mes" && (
              <MonthView
                anchor={anchor}
                events={events}
                onSelectEvent={handleSelectEvent}
                onCreateAt={handleCreateAt}
              />
            )}
          </>
        )}

        <Legenda />
      </div>

      <EventoDetailsSlideOver
        event={selected}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />
    </>
  );
}

// ── Sub-componentes ─────────────────────────────────────────────────────────

function ViewSwitcher({
  value,
  onChange,
}: {
  value: ViewMode;
  onChange: (v: ViewMode) => void;
}) {
  return (
    <div
      className="inline-flex items-center rounded-md border border-border p-0.5"
      role="tablist"
      aria-label="Modo de visualização"
    >
      {VIEW_MODES.map((mode) => {
        const active = mode.value === value;
        return (
          <button
            key={mode.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(mode.value)}
            className={`inline-flex h-7 items-center rounded px-3 text-xs font-medium transition ${
              active
                ? "bg-primary text-surface"
                : "text-text-muted hover:bg-surface-muted hover:text-text"
            }`}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}

const STATUS_LEGENDA_ORDEM: [string, string][] = [
  ["planejado", "Planejado"],
  ["agendado", "Agendado"],
  ["em_andamento", "Em andamento"],
  ["concluido", "Concluído"],
  ["concluido_sem_evidencia", "Sem evidência"],
  ["adiada", "Adiada"],
  ["nao_realizada", "Não realizada"],
  ["cancelada", "Cancelada"],
];

function Legenda() {
  return (
    <details className="rounded-lg border border-border bg-surface p-3">
      <summary className="cursor-pointer text-xs font-medium text-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
          Legenda de cores por status
        </span>
      </summary>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-text-muted">
        {STATUS_LEGENDA_ORDEM.map(([key, label]) => (
          <li key={key} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: STATUS_HEX_COLORS[key] }}
              aria-hidden="true"
            />
            {label}
          </li>
        ))}
      </ul>
    </details>
  );
}
