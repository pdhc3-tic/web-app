"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Filter, MapPinOff, Plus } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Button } from "@/app/components/ui/Button/Button";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { MapView, type MapMarker } from "@/app/components/sgp/MapView/MapView";
import {
  fetchMunicipalityOptions,
  fetchTerritoryOptions,
  type StatusUpfFilter,
} from "@/app/lib/upfs";
import { ViewToggle } from "../../_components/ViewToggle";
import {
  UpfsFilters,
  type UpfsFiltersValue,
} from "../../_components/UpfsFilters";
import { fetchUpfsMapaMock, type UpfMapa, type UpfMapaResponse } from "../_mock/mapaMock";
import { UpfMiniFichaSlideOver } from "./UpfMiniFichaSlideOver";

const DEFAULT_FILTERS: UpfsFiltersValue = {
  search: "",
  municipio: "",
  territorio: "",
  projeto: "",
  status: "ativas",
  cadastradoDe: "",
  cadastradoAte: "",
};

function parseStatus(value: string | null): StatusUpfFilter {
  return value === "inativas" || value === "todas" ? value : "ativas";
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function UpfsMapaContent() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const [filters, setFilters] = useState<UpfsFiltersValue>(() => ({
    search: searchParams.get("q") ?? "",
    municipio: searchParams.get("municipio") ?? "",
    territorio: searchParams.get("territorio") ?? "",
    projeto: searchParams.get("projeto") ?? "",
    status: parseStatus(searchParams.get("status")),
    cadastradoDe: searchParams.get("de") ?? "",
    cadastradoAte: searchParams.get("ate") ?? "",
  }));

  const [data, setData] = useState<UpfMapaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [municipioOptions, setMunicipioOptions] = useState<SelectOption[]>([]);
  const [territorioOptions, setTerritorioOptions] = useState<SelectOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);

  const [filtersDrawerOpen, setFiltersDrawerOpen] = useState(false);
  const [selected, setSelected] = useState<UpfMapa | null>(null);

  const hasActiveFilters = useMemo(() => {
    return (
      filters.search.trim() !== "" ||
      filters.municipio !== "" ||
      filters.territorio !== "" ||
      filters.projeto !== "" ||
      filters.status !== DEFAULT_FILTERS.status ||
      filters.cadastradoDe !== "" ||
      filters.cadastradoAte !== ""
    );
  }, [filters]);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (filters.search.trim()) qs.set("q", filters.search.trim());
    if (filters.municipio) qs.set("municipio", filters.municipio);
    if (filters.territorio) qs.set("territorio", filters.territorio);
    if (filters.projeto) qs.set("projeto", filters.projeto);
    if (filters.status !== "ativas") qs.set("status", filters.status);
    if (filters.cadastradoDe) qs.set("de", filters.cadastradoDe);
    if (filters.cadastradoAte) qs.set("ate", filters.cadastradoAte);
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [filters, pathname, router]);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOptionsLoading(true);
    Promise.all([
      fetchMunicipalityOptions(controller.signal),
      fetchTerritoryOptions(controller.signal),
    ])
      .then(([m, t]) => {
        setMunicipioOptions(m);
        setTerritorioOptions(t);
      })
      .catch(() => {})
      .finally(() => setOptionsLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    fetchUpfsMapaMock(
      {
        search: filters.search || undefined,
        municipio: filters.municipio || undefined,
        territorio: filters.territorio || undefined,
        projeto: filters.projeto || undefined,
        status: filters.status,
      },
      controller.signal,
    )
      .then((res) => setData(res))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Não foi possível carregar o mapa.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [
    filters.search,
    filters.municipio,
    filters.territorio,
    filters.projeto,
    filters.status,
    reloadKey,
  ]);

  const markers: MapMarker[] = useMemo(() => {
    if (!data) return [];
    return data.results.map((u) => ({
      id: u.id,
      position: [u.latitude, u.longitude] as [number, number],
      status: u.ativa ? "active" : "inactive",
      popup: (
        <div>
          <p className="font-medium text-text">{u.nome_titular}</p>
          <p className="text-xs text-text-muted">{u.municipio}{u.territorio ? ` · ${u.territorio}` : ""}</p>
        </div>
      ),
    }));
  }, [data]);

  const handleFilterChange = useCallback(
    (patch: Partial<UpfsFiltersValue>) => {
      setFilters((prev) => ({ ...prev, ...patch }));
    },
    [],
  );

  const handleClearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const handleMarkerClick = useCallback(
    (id: MapMarker["id"]) => {
      const upf = data?.results.find((u) => u.id === id);
      if (upf) setSelected(upf);
    },
    [data],
  );

  return (
    <>
      <PageHeader>
        <div className="flex w-full items-center justify-between gap-3">
          <h1 className="truncate text-base font-semibold text-text">UPFs</h1>
          <div className="flex items-center gap-2">
            <ViewToggle active="mapa" />
            <Button
              size="sm"
              variant="secondary"
              leftIcon={<Filter className="h-4 w-4" />}
              onClick={() => setFiltersDrawerOpen(true)}
            >
              Filtros{hasActiveFilters ? " •" : ""}
            </Button>
            <Link href="/sgp/upfs/nova/">
              <Button size="sm" leftIcon={<Plus className="h-4 w-4" />}>Nova UPF</Button>
            </Link>
          </div>
        </div>
      </PageHeader>

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UPFs", href: "/sgp/upfs/" },
            { label: "Mapa" },
          ]}
        />

        {error && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
          >
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </span>
            <Button variant="secondary" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Tentar novamente
            </Button>
          </div>
        )}

        {data?.truncated && (
          <div
            role="status"
            className="rounded-md border border-warning-text bg-warning-bg px-3 py-2 text-sm text-warning-text"
          >
            Mostrando {data.results.length} de {data.total} UPFs — aproxime o zoom para ver mais detalhes.
          </div>
        )}

        <div className="relative">
          {loading && (
            <div className="pointer-events-none absolute right-3 top-3 z-10 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-text-muted shadow-sm">
              <Spinner className="h-3 w-3 animate-spin" />
              Carregando...
            </div>
          )}

          {!loading && !error && markers.length === 0 ? (
            <EmptyMap />
          ) : (
            <MapView
              markers={markers}
              height="calc(100vh - 220px)"
              ariaLabel="Mapa de UPFs"
              onMarkerClick={handleMarkerClick}
            />
          )}
        </div>
      </div>

      <SlideOver
        open={filtersDrawerOpen}
        onClose={() => setFiltersDrawerOpen(false)}
        title="Filtros"
        footer={
          <div className="flex items-center justify-between gap-2">
            <Button variant="ghost" onClick={handleClearFilters} disabled={!hasActiveFilters}>
              Limpar
            </Button>
            <Button onClick={() => setFiltersDrawerOpen(false)}>Aplicar</Button>
          </div>
        }
      >
        <div className="p-4">
          <UpfsFilters
            value={filters}
            onChange={handleFilterChange}
            onClear={handleClearFilters}
            hasActiveFilters={hasActiveFilters}
            municipioOptions={municipioOptions}
            territorioOptions={territorioOptions}
            optionsLoading={optionsLoading}
          />
        </div>
      </SlideOver>

      <UpfMiniFichaSlideOver upf={selected} onClose={() => setSelected(null)} />
    </>
  );
}

function EmptyMap() {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border bg-surface-muted p-8 text-center"
      style={{ minHeight: "calc(100vh - 220px)" }}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface text-text-muted">
        <MapPinOff className="h-6 w-6" />
      </span>
      <p className="text-sm font-medium text-text">Nenhuma UPF georreferenciada</p>
      <p className="max-w-sm text-xs text-text-muted">
        UPFs sem GPS não aparecem no mapa. Ative o GPS no cadastro para visualizá-las aqui.
      </p>
    </div>
  );
}

export default function UpfsMapaView() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <UpfsMapaContent />
    </Suspense>
  );
}
