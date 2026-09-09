"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, SearchX, Sprout } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { Select } from "@/app/components/ui/Select/Select";
import Spinner from "@/app/components/icons/Spinner";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import {
  fetchIndicadoresProducao,
  listProducaoConsolidada,
  TIPO_OPTIONS,
  type IndicadoresProducao,
  type ProducaoConsolidadaItem,
} from "@/app/lib/producao";
import { fetchTerritoryOptions, fetchMunicipalityOptions } from "@/app/lib/upfs";

const DEFAULT_LIMIT = 20;
const PAGE_SIZES = [20, 50, 100];

type Filters = {
  tipo: string;
  municipio: string;
  territorio: string;
};

const EMPTY_FILTERS: Filters = { tipo: "", municipio: "", territorio: "" };

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function tipoLabel(tipo: string): string {
  return TIPO_OPTIONS.find((o) => o.value === tipo)?.label ?? tipo;
}

function IndicadoresBar({ indicadores }: { indicadores: IndicadoresProducao }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
          UPFs produtoras
        </p>
        <p className="mt-1 text-2xl font-semibold text-text">
          {indicadores.total_upfs_produtoras}
        </p>
      </div>
      {indicadores.area_total_ha && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Área total (ha)
          </p>
          <p className="mt-1 text-2xl font-semibold text-text">
            {Number(indicadores.area_total_ha).toLocaleString("pt-BR", {
              maximumFractionDigits: 1,
            })}
          </p>
        </div>
      )}
      {indicadores.principais_culturas.length > 0 && (
        <div className="col-span-full rounded-lg border border-border bg-surface p-4 sm:col-span-1">
          <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Principais culturas
          </p>
          <div className="mt-2 flex flex-wrap gap-1">
            {indicadores.principais_culturas.slice(0, 5).map((c) => (
              <Chip key={c.nome}>{c.nome}</Chip>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProducaoView() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const [filters, setFilters] = useState<Filters>(() => ({
    tipo: searchParams.get("tipo") ?? "",
    municipio: searchParams.get("municipio") ?? "",
    territorio: searchParams.get("territorio") ?? "",
  }));
  const [limit, setLimit] = useState<number>(() => {
    const l = Number(searchParams.get("limit"));
    return PAGE_SIZES.includes(l) ? l : DEFAULT_LIMIT;
  });
  const [offset, setOffset] = useState<number>(() => {
    const o = Number(searchParams.get("offset"));
    return Number.isFinite(o) && o > 0 ? o : 0;
  });

  const [items, setItems] = useState<ProducaoConsolidadaItem[]>([]);
  const [count, setCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [indicadores, setIndicadores] = useState<IndicadoresProducao | null>(null);

  const [territorioOptions, setTerritorioOptions] = useState<SelectOption[]>([]);
  const [municipioOptions, setMunicipioOptions] = useState<SelectOption[]>([]);

  const hasActiveFilters = Object.values(filters).some((v) => v !== "");

  useEffect(() => {
    const qs = new URLSearchParams();
    if (filters.tipo) qs.set("tipo", filters.tipo);
    if (filters.municipio) qs.set("municipio", filters.municipio);
    if (filters.territorio) qs.set("territorio", filters.territorio);
    if (limit !== DEFAULT_LIMIT) qs.set("limit", String(limit));
    if (offset > 0) qs.set("offset", String(offset));
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [filters, limit, offset, pathname, router]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchTerritoryOptions(controller.signal).catch(() => [] as SelectOption[]),
      fetchMunicipalityOptions(controller.signal).catch(() => [] as SelectOption[]),
    ]).then(([territorios, municipios]) => {
      if (controller.signal.aborted) return;
      setTerritorioOptions(territorios);
      setMunicipioOptions(municipios);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchIndicadoresProducao(
      { territorio: filters.territorio || undefined, municipio: filters.municipio || undefined },
      controller.signal,
    )
      .then((data) => { if (!controller.signal.aborted) setIndicadores(data); })
      .catch(() => {});
    return () => controller.abort();
  }, [filters.territorio, filters.municipio, reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    setDataLoading(true);
    setError(null);
    listProducaoConsolidada(
      {
        limit,
        offset,
        tipo: filters.tipo || undefined,
        municipio: filters.municipio || undefined,
        territorio: filters.territorio || undefined,
      },
      controller.signal,
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        setItems(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError ? e.message : "Não foi possível carregar a produção.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });
    return () => controller.abort();
  }, [limit, offset, filters, reloadKey]);

  const handleFilterChange = useCallback((patch: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    setOffset(0);
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGP", href: "/sgp" },
          { label: "Produção da UPF" },
        ]}
      />

      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">
          Produção da UPF
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Visão consolidada das atividades produtivas por território.
        </p>
      </div>

      {indicadores && <IndicadoresBar indicadores={indicadores} />}

      <div className="flex flex-wrap items-end gap-3">
        <Select
          label="Tipo"
          options={TIPO_OPTIONS as unknown as SelectOption[]}
          value={filters.tipo}
          onChange={(v) => handleFilterChange({ tipo: v })}
          placeholder="Todos"
        />
        <Select
          label="Município"
          options={municipioOptions}
          value={filters.municipio}
          onChange={(v) => handleFilterChange({ municipio: v })}
          placeholder="Todos"
        />
        <Select
          label="Território"
          options={territorioOptions}
          value={filters.territorio}
          onChange={(v) => handleFilterChange({ territorio: v })}
          placeholder="Todos"
        />
        {hasActiveFilters && (
          <button
            type="button"
            onClick={() => { setFilters(EMPTY_FILTERS); setOffset(0); }}
            className="text-sm text-text-muted hover:text-text"
          >
            Limpar
          </button>
        )}
      </div>

      {dataLoading ? (
        <CenteredSpinner />
      ) : error ? (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">{error}</p>
          <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)}>
            Tentar novamente
          </Button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<SearchX className="h-8 w-8" />}
          title={hasActiveFilters ? "Nenhum registro encontrado" : "Nenhuma produção cadastrada"}
          description={
            hasActiveFilters
              ? "Tente ajustar os filtros."
              : "Cadastre atividades produtivas nas fichas das UPFs."
          }
          action={
            hasActiveFilters ? (
              <Button
                variant="secondary"
                onClick={() => { setFilters(EMPTY_FILTERS); setOffset(0); }}
              >
                Limpar filtros
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 z-10 bg-surface-muted">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">
                    UPF / Titular
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">
                    Tipo
                  </th>
                  <th className="hidden px-4 py-3 text-left font-medium text-text-muted md:table-cell">
                    Cultura / Espécie
                  </th>
                  <th className="hidden px-4 py-3 text-left font-medium text-text-muted md:table-cell">
                    Município
                  </th>
                  <th className="hidden px-4 py-3 text-left font-medium text-text-muted lg:table-cell">
                    Território
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-surface">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-surface-muted">
                    <td className="px-4 py-3 font-medium text-text">
                      <Link
                        href={`/sgp/upfs/${item.upf_id}#producao`}
                        className="hover:underline"
                      >
                        {item.upf_nome_titular || "—"}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-text-muted">
                      {tipoLabel(item.tipo)}
                    </td>
                    <td className="hidden px-4 py-3 text-text-muted md:table-cell">
                      {item.cultura?.nome ?? item.especie?.nome ?? "—"}
                    </td>
                    <td className="hidden px-4 py-3 text-text-muted md:table-cell">
                      {item.municipio || "—"}
                    </td>
                    <td className="hidden px-4 py-3 lg:table-cell">
                      {item.territorio ? (
                        <Chip>{item.territorio}</Chip>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {count > limit && (
            <Pagination
              count={count}
              limit={limit}
              offset={offset}
              pageSizes={PAGE_SIZES}
              onOffsetChange={setOffset}
              onLimitChange={(l) => { setLimit(l); setOffset(0); }}
            />
          )}
        </>
      )}
    </div>
  );
}

export default function ProducaoPage() {
  return (
    <>
      <PageHeader>
        <div className="flex items-center gap-2">
          <Sprout className="h-5 w-5 text-text-muted" />
          <span className="truncate text-base font-semibold text-text">
            Produção da UPF
          </span>
        </div>
      </PageHeader>
      <Suspense fallback={<CenteredSpinner />}>
        <ProducaoView />
      </Suspense>
    </>
  );
}
