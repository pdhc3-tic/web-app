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
import {
  fetchDispositivoOptions,
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
  device: "",
  comErro: false,
};

/**
 * Tela do Log de Sincronização SCA (#157). Consome
 * `GET /api/v1/sca/sync-events/` — Super Admin/UGP no backend.
 *
 * Aceita `?device={id}` na URL para pré-filtrar por dispositivo — é o link
 * emitido pelo painel #156 ao clicar num dispositivo específico.
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
  // O deep-link do #156 chega em `?device=` — inicializa o filtro a partir
  // dele. Como a inicialização é feita na primeira renderização (useState
  // lazy), mudanças posteriores na URL não sobrescrevem o filtro escolhido
  // pelo usuário — é intencional; querystring é só o ponto de entrada.
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<SyncEventsFiltrosValue>(() => ({
    ...DEFAULT_FILTERS,
    device: searchParams.get("device") ?? "",
  }));

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

  // Zera offset quando filtros mudam.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0);
  }, [filters.de, filters.ate, filters.device, filters.comErro]);

  // Options do select de dispositivo — falha silenciosa (o 403 principal
  // vem do endpoint de eventos e cuida da tela de bloqueio).
  useEffect(() => {
    const controller = new AbortController();
    fetchDispositivoOptions(controller.signal)
      .then(setDispositivoOptions)
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
        // Datas locais viram range em UTC — mesmo pattern usado em users.ts.
        iniciadoDe: filters.de ? `${filters.de}T00:00:00Z` : undefined,
        iniciadoAte: filters.ate ? `${filters.ate}T23:59:59Z` : undefined,
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
                  ? "Ajuste o período ou o dispositivo e tente novamente."
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
