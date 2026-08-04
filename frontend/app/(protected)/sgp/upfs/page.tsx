"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import { AlertTriangle, Plus, SearchX, Users } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Button } from "@/app/components/ui/Button/Button";
import Spinner from "@/app/components/icons/Spinner";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { ApiError } from "@/app/lib/api";
import {
  listUpfs,
  fetchMunicipalityOptions,
  fetchTerritoryOptions,
  type StatusUpfFilter,
  type UpfListItem,
} from "@/app/lib/upfs";
import {
  UpfsFilters,
  type UpfsFiltersValue,
} from "./_components/UpfsFilters";
import { UpfsTable } from "./_components/UpfsTable";
import { ViewToggle } from "./_components/ViewToggle";

const SEARCH_DEBOUNCE_MS = 300;
const DEFAULT_LIMIT = 50;
const PAGE_SIZES = [25, 50, 100];

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

function UpfsView() {
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
  const [debouncedSearch, setDebouncedSearch] = useState(
    () => searchParams.get("q") ?? "",
  );
  const [limit, setLimit] = useState<number>(() => {
    const l = Number(searchParams.get("limit"));
    return PAGE_SIZES.includes(l) ? l : DEFAULT_LIMIT;
  });
  const [offset, setOffset] = useState<number>(() => {
    const o = Number(searchParams.get("offset"));
    return Number.isFinite(o) && o > 0 ? o : 0;
  });

  const [upfs, setUpfs] = useState<UpfListItem[]>([]);
  const [count, setCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [municipioOptions, setMunicipioOptions] = useState<SelectOption[]>([]);
  const [territorioOptions, setTerritorioOptions] = useState<SelectOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);

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
    const t = setTimeout(() => {
      setDebouncedSearch(filters.search);
      setOffset(0);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [filters.search]);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (debouncedSearch.trim()) qs.set("q", debouncedSearch.trim());
    if (filters.municipio) qs.set("municipio", filters.municipio);
    if (filters.territorio) qs.set("territorio", filters.territorio);
    if (filters.projeto) qs.set("projeto", filters.projeto);
    if (filters.status !== "ativas") qs.set("status", filters.status);
    if (filters.cadastradoDe) qs.set("de", filters.cadastradoDe);
    if (filters.cadastradoAte) qs.set("ate", filters.cadastradoAte);
    if (limit !== DEFAULT_LIMIT) qs.set("limit", String(limit));
    if (offset > 0) qs.set("offset", String(offset));
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
  }, [
    debouncedSearch,
    filters.municipio,
    filters.territorio,
    filters.projeto,
    filters.status,
    filters.cadastradoDe,
    filters.cadastradoAte,
    limit,
    offset,
    pathname,
    router,
  ]);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOptionsLoading(true);
    Promise.all([
      fetchMunicipalityOptions(controller.signal),
      fetchTerritoryOptions(controller.signal),
    ])
      .then(([municipios, territorios]) => {
        setMunicipioOptions(municipios);
        setTerritorioOptions(territorios);
      })
      .catch(() => {
        /* filtros seguem vazios; a listagem ainda funciona */
      })
      .finally(() => setOptionsLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listUpfs(
      {
        limit,
        offset,
        search: debouncedSearch,
        municipio: filters.municipio || undefined,
        territorio: filters.territorio || undefined,
        projeto: filters.projeto || undefined,
        status: filters.status,
        cadastradoDe: filters.cadastradoDe || undefined,
        cadastradoAte: filters.cadastradoAte || undefined,
        ordering: "-criado_em",
      },
      controller.signal,
    )
      .then((data) => {
        setUpfs(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as UPFs. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [
    limit,
    offset,
    debouncedSearch,
    filters.municipio,
    filters.territorio,
    filters.projeto,
    filters.status,
    filters.cadastradoDe,
    filters.cadastradoAte,
    reloadKey,
  ]);

  const handleFilterChange = useCallback(
    (patch: Partial<UpfsFiltersValue>) => {
      setFilters((prev) => ({ ...prev, ...patch }));
      if (!("search" in patch)) setOffset(0);
    },
    [],
  );

  const handleClearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setDebouncedSearch("");
    setOffset(0);
  }, []);

  const handleLimitChange = useCallback((newLimit: number) => {
    setLimit(newLimit);
    setOffset(0);
  }, []);

  const handleNewUpf = useCallback(() => {
    router.push("/sgp/upfs/nova/");
  }, [router]);

  const showEmpty = !dataLoading && !error && upfs.length === 0;

  return (
    <>
      <PageHeader>
        <div className="flex w-full items-center justify-between gap-3">
          <h1 className="truncate text-base font-semibold text-text">UPFs</h1>
          <div className="flex items-center gap-2">
            <ViewToggle active="lista" />
            <Button
              size="sm"
              onClick={handleNewUpf}
              leftIcon={<Plus className="h-4 w-4" />}
            >
              Nova UPF
            </Button>
          </div>
        </div>
      </PageHeader>

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UPFs" },
          ]}
        />

        <UpfsFilters
          value={filters}
          onChange={handleFilterChange}
          onClear={handleClearFilters}
          hasActiveFilters={hasActiveFilters}
          municipioOptions={municipioOptions}
          territorioOptions={territorioOptions}
          optionsLoading={optionsLoading}
        />

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">
              Não foi possível carregar as UPFs. {error}
            </p>
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        ) : showEmpty ? (
          <div className="rounded-lg border border-border bg-surface">
            {hasActiveFilters ? (
              <EmptyState
                icon={<SearchX className="h-7 w-7" />}
                title="Nenhuma UPF corresponde aos filtros"
                description="Tente ajustar os filtros ou limpar tudo para ver todas as UPFs."
                action={
                  <Button variant="secondary" onClick={handleClearFilters}>
                    Limpar filtros
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={<Users className="h-7 w-7" />}
                title="Nenhuma UPF cadastrada ainda"
                description="Comece cadastrando a primeira família / unidade produtiva familiar."
                action={
                  <Button
                    variant="primary"
                    onClick={handleNewUpf}
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    Nova UPF
                  </Button>
                }
              />
            )}
          </div>
        ) : (
          <>
            <UpfsTable upfs={upfs} loading={dataLoading} />
            <Pagination
              count={count}
              offset={offset}
              limit={limit}
              onOffsetChange={setOffset}
              onLimitChange={handleLimitChange}
              itemNoun={{ one: "UPF", other: "UPFs" }}
            />
          </>
        )}
      </div>
    </>
  );
}

export default function UpfsPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <UpfsView />
    </Suspense>
  );
}
