"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ClipboardList } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import { localDayEndISO, localDayStartISO } from "@/app/lib/datetime";
import {
  fetchSyncEventsFiltroOptions,
  listSyncEvents,
  type SyncEventListItem,
} from "@/app/lib/sca";
import {
  SyncEventsFiltros,
  type SyncEventsFiltrosValue,
} from "./_components/SyncEventsFiltros";
import { SyncEventsTable } from "./_components/SyncEventsTable";

const DEFAULT_LIMIT = 25;
const PAGE_SIZES = [25, 50, 100];

const DEFAULT_FILTERS: SyncEventsFiltrosValue = {
  de: "",
  ate: "",
  tecnico: "",
  device: "",
  comErro: false,
};

/** Chaves espelhadas na querystring, na ordem em que aparecem na tela. */
const FILTER_QS_KEYS = ["de", "ate", "tecnico", "device"] as const;

function readFiltersFromSearchParams(
  params: URLSearchParams,
): SyncEventsFiltrosValue {
  return {
    de: params.get("de") ?? "",
    ate: params.get("ate") ?? "",
    tecnico: params.get("tecnico") ?? "",
    device: params.get("device") ?? "",
    comErro: params.get("com_erro") === "1",
  };
}

/**
 * Reflete os filtros na URL, preservando query params alheios a este conjunto.
 * `replaceState` em vez de push: filtrar não é navegação, e cada tecla numa
 * data viraria uma entrada no histórico do browser. Mesmo padrão do
 * FormulariosTab da ficha da UPF.
 */
function syncFiltersToUrl(filters: SyncEventsFiltrosValue) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  for (const key of FILTER_QS_KEYS) {
    const value = filters[key];
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  if (filters.comErro) url.searchParams.set("com_erro", "1");
  else url.searchParams.delete("com_erro");
  window.history.replaceState(
    null,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
}

/**
 * Tela do Log de Sincronização SCA (#157). Consome
 * `GET /api/v1/sca/sync-events/` — Super Admin/UGP no backend.
 *
 * Todos os filtros vivem na querystring (`?de=&ate=&tecnico=&device=&com_erro=`)
 * — sobrevivem ao reload e podem ser compartilhados por link. `?device={id}`
 * continua sendo o deep-link emitido pelo painel #156.
 */
export default function SyncEventsPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <SyncEventsView />
    </Suspense>
  );
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function SyncEventsView() {
  // A querystring é lida uma vez, na primeira renderização (useState lazy): a
  // partir daí quem manda é o estado, e é ele que reescreve a URL. Ler a cada
  // render criaria um laço com o replaceState logo abaixo.
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<SyncEventsFiltrosValue>(() =>
    readFiltersFromSearchParams(new URLSearchParams(searchParams.toString())),
  );

  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  const [events, setEvents] = useState<SyncEventListItem[]>([]);
  const [count, setCount] = useState(0);

  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [dispositivoOptions, setDispositivoOptions] = useState<SelectOption[]>(
    [],
  );
  const [tecnicoOptions, setTecnicoOptions] = useState<SelectOption[]>([]);

  // Zera offset quando filtros mudam — inclusive o técnico, senão trocar o
  // filtro na página 3 pediria um offset que o novo recorte não tem.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0);
  }, [
    filters.de,
    filters.ate,
    filters.tecnico,
    filters.device,
    filters.comErro,
  ]);

  useEffect(() => {
    syncFiltersToUrl(filters);
  }, [filters]);

  // Options dos selects — uma requisição só para os dois. Falha silenciosa (o
  // 403 principal vem do endpoint de eventos e cuida da tela de bloqueio).
  useEffect(() => {
    const controller = new AbortController();
    fetchSyncEventsFiltroOptions(controller.signal)
      .then(({ dispositivos, tecnicos }) => {
        setDispositivoOptions(dispositivos);
        setTecnicoOptions(tecnicos);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listSyncEvents(
      {
        limit,
        offset,
        // Datas do input <type=date> são LOCAIS; convertidas para ISO em UTC
        // preservando o fuso do navegador. Ver localDayStartISO/localDayEndISO.
        iniciadoDe: localDayStartISO(filters.de),
        iniciadoAte: localDayEndISO(filters.ate),
        user: filters.tecnico ? Number(filters.tecnico) : undefined,
        device: filters.device ? Number(filters.device) : undefined,
        comErro: filters.comErro ? true : undefined,
      },
      controller.signal,
    )
      .then((res) => {
        setEvents(res.results);
        setCount(res.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o log de sincronização. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [limit, offset, filters, reloadKey]);

  const hasActiveFilters = useMemo(
    () =>
      filters.de !== "" ||
      filters.ate !== "" ||
      filters.tecnico !== "" ||
      filters.device !== "" ||
      filters.comErro,
    [filters],
  );

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Log de Sincronização
      </h1>
    </PageHeader>
  );

  if (forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const showEmpty = !dataLoading && !error && events.length === 0;
  const isFirstLoad = dataLoading && events.length === 0;

  return (
    <div data-testid="sca-sync-events-page">
      {header}
      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SCA", href: "/sca" },
            { label: "Log de Sincronização" },
          ]}
        />

        <p className="text-sm text-text-muted">
          Histórico de operações de sincronização (push/pull/refresh) por
          técnico e dispositivo, ordenado do mais recente para o mais antigo.
        </p>

        <SyncEventsFiltros
          value={filters}
          onChange={setFilters}
          dispositivoOptions={dispositivoOptions}
          tecnicoOptions={tecnicoOptions}
          disabled={isFirstLoad}
        />

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        ) : isFirstLoad ? (
          <CenteredSpinner />
        ) : showEmpty ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<ClipboardList className="h-7 w-7" />}
              title={
                hasActiveFilters
                  ? "Nenhum evento com esses filtros"
                  : "Nenhuma sincronização registrada ainda."
              }
              description={
                hasActiveFilters
                  ? "Ajuste o período, o técnico ou o dispositivo e tente novamente."
                  : "Quando um dispositivo SCA fizer o primeiro push ou pull, o evento aparecerá aqui."
              }
              action={
                hasActiveFilters ? (
                  <Button
                    variant="secondary"
                    onClick={() => setFilters(DEFAULT_FILTERS)}
                  >
                    Limpar filtros
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <>
            <SyncEventsTable events={events} loading={dataLoading} />
            <Pagination
              count={count}
              offset={offset}
              limit={limit}
              onOffsetChange={setOffset}
              onLimitChange={(l) => {
                setLimit(l);
                setOffset(0);
              }}
              pageSizes={PAGE_SIZES}
              itemNoun={{ one: "evento", other: "eventos" }}
            />
          </>
        )}
      </div>
    </div>
  );
}
