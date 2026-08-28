"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Smartphone } from "lucide-react";
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
  fetchScaTerritoryOptions,
  listDevices,
  type SyncDeviceListItem,
} from "@/app/lib/sca";
import { DispositivosTable } from "./_components/DispositivosTable";
import {
  DispositivosFiltros,
  type DispositivosFiltrosValue,
} from "./_components/DispositivosFiltros";
import { DispositivoDetalheSlideOver } from "./_components/DispositivoDetalheSlideOver";

const SEARCH_DEBOUNCE_MS = 300;
const DEFAULT_LIMIT = 25;
const PAGE_SIZES = [25, 50, 100];

const DEFAULT_FILTERS: DispositivosFiltrosValue = {
  search: "",
  territorio: "",
};

/**
 * Painel de Monitoramento de Dispositivos SCA (#156).
 *
 * Consome `GET /api/v1/sca/devices/` — endpoint restrito a Super Admin/UGP no
 * backend. Quando o usuário não tem permissão, o próprio backend devolve 403
 * e a tela cai em <RestrictedAccess/> em vez de checar perfil no cliente
 * (evita divergência entre a matriz do backend e uma cópia no front).
 *
 * O semáforo (verde/laranja/vermelho) é derivado no cliente a partir de
 * `ultimo_sync_servidor` + `limiar_alerta_dias` — decisão registrada em
 * backend/apps/sca/README.md, sem campo dedicado no modelo.
 */
export default function DispositivosSCAPage() {
  const [filters, setFilters] = useState<DispositivosFiltrosValue>(DEFAULT_FILTERS);
  // `search` propaga com atraso para não disparar uma request a cada tecla.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  const [devices, setDevices] = useState<SyncDeviceListItem[]>([]);
  const [count, setCount] = useState(0);
  const [limiarAlertaDias, setLimiarAlertaDias] = useState<number>(7);

  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [territoryOptions, setTerritoryOptions] = useState<SelectOption[]>([]);

  const [detalheDevice, setDetalheDevice] = useState<SyncDeviceListItem | null>(
    null,
  );

  // ── Debounce da busca ──────────────────────────────────────────────────────
  useEffect(() => {
    const id = window.setTimeout(() => {
      setDebouncedSearch(filters.search.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [filters.search]);

  // Qualquer mudança relevante para o backend zera o offset. É válido resetar
  // o offset aqui porque o efeito só dispara quando o critério muda, não a
  // cada render (o hook lint sinaliza como padrão — supressão intencional).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0);
  }, [debouncedSearch, filters.territorio]);

  // ── Carga das opções de território (uma vez) ───────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    fetchScaTerritoryOptions(controller.signal)
      .then(setTerritoryOptions)
      .catch(() => {
        // Falha aqui não bloqueia a tela — o filtro fica sem opções, mas a
        // listagem principal continua funcional. O 403 do endpoint de devices
        // já cuida do gate de acesso.
      });
    return () => controller.abort();
  }, []);

  // ── Carga da listagem ──────────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listDevices(
      {
        limit,
        offset,
        search: debouncedSearch || undefined,
        territorio: filters.territorio
          ? Number(filters.territorio)
          : undefined,
      },
      controller.signal,
    )
      .then((res) => {
        setDevices(res.results);
        setCount(res.count);
        setLimiarAlertaDias(res.limiar_alerta_dias);
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
            : "Não foi possível carregar os dispositivos. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [limit, offset, debouncedSearch, filters.territorio, reloadKey]);

  const hasActiveFilters = useMemo(
    () => debouncedSearch !== "" || filters.territorio !== "",
    [debouncedSearch, filters.territorio],
  );

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Monitoramento de Dispositivos
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

  const showEmpty = !dataLoading && !error && devices.length === 0;
  const isFirstLoad = dataLoading && devices.length === 0;

  return (
    <div data-testid="sca-dispositivos-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SCA", href: "/sca" },
            { label: "Dispositivos" },
          ]}
        />

        <p className="text-sm text-text-muted">
          Situação de sincronização dos dispositivos usados pelos técnicos em
          campo. Dispositivos sem sincronizar há mais de{" "}
          <strong className="text-text">{limiarAlertaDias} dias</strong> ficam
          em vermelho; com pendências acumuladas, em laranja.
        </p>

        <DispositivosFiltros
          value={filters}
          onChange={setFilters}
          territorioOptions={territoryOptions}
          disabled={dataLoading && isFirstLoad}
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
          <div className="flex min-h-[40vh] items-center justify-center">
            <Spinner className="h-6 w-6 animate-spin text-text-muted" />
          </div>
        ) : showEmpty ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Smartphone className="h-7 w-7" />}
              title={
                hasActiveFilters
                  ? "Nenhum dispositivo com esses filtros"
                  : "Nenhum dispositivo sincronizado ainda."
              }
              description={
                hasActiveFilters
                  ? "Ajuste os filtros e tente novamente."
                  : "Quando um técnico de campo abrir o app SCA e autenticar, o dispositivo aparecerá aqui."
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
            <DispositivosTable
              devices={devices}
              limiarAlertaDias={limiarAlertaDias}
              loading={dataLoading}
              onRowClick={setDetalheDevice}
            />
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
              itemNoun={{ one: "dispositivo", other: "dispositivos" }}
            />
          </>
        )}
      </div>

      <DispositivoDetalheSlideOver
        open={detalheDevice !== null}
        onClose={() => setDetalheDevice(null)}
        device={detalheDevice}
        limiarAlertaDias={limiarAlertaDias}
      />
    </div>
  );
}
