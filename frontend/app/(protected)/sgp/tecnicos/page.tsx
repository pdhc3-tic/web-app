"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, SearchX, UserCog } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import Spinner from "@/app/components/icons/Spinner";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import { canManageWorkPlan } from "@/app/lib/auth/roles";
import {
  fetchOscOptions,
  fetchUserOptions,
  listTecnicosSGP,
  type TecnicoListItem,
} from "@/app/lib/tecnicos";
import { fetchTerritoryOptions } from "@/app/lib/upfs";
import { useSession } from "next-auth/react";
import {
  EMPTY_FILTERS,
  TecnicosFilters,
  type TecnicosFiltersValue,
} from "./_components/TecnicosFilters";
import { TecnicosTable } from "./_components/TecnicosTable";
import {
  TecnicoSlideOver,
  type TecnicoSlideOverMode,
} from "./_components/TecnicoSlideOver";

const DEFAULT_LIMIT = 20;
const PAGE_SIZES = [20, 50, 100];

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function TecnicosView() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();

  const canWrite = canManageWorkPlan(session?.user);

  const [filters, setFilters] = useState<TecnicosFiltersValue>(() => ({
    territorio: searchParams.get("territorio") ?? "",
    osc: searchParams.get("osc") ?? "",
    papel: searchParams.get("papel") ?? "",
    ativo: searchParams.get("ativo") ?? "",
  }));
  const [limit, setLimit] = useState<number>(() => {
    const l = Number(searchParams.get("limit"));
    return PAGE_SIZES.includes(l) ? l : DEFAULT_LIMIT;
  });
  const [offset, setOffset] = useState<number>(() => {
    const o = Number(searchParams.get("offset"));
    return Number.isFinite(o) && o > 0 ? o : 0;
  });

  const [tecnicos, setTecnicos] = useState<TecnicoListItem[]>([]);
  const [count, setCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [territorioOptions, setTerritorioOptions] = useState<SelectOption[]>([]);
  const [oscOptions, setOscOptions] = useState<SelectOption[]>([]);
  const [userOptions, setUserOptions] = useState<SelectOption[]>([]);

  const [slideOver, setSlideOver] = useState<{
    open: boolean;
    mode: TecnicoSlideOverMode;
    tecnico?: TecnicoListItem;
  }>({ open: false, mode: "view" });

  const hasActiveFilters =
    Object.values(filters).some((v) => v !== "");

  useEffect(() => {
    const qs = new URLSearchParams();
    if (filters.territorio) qs.set("territorio", filters.territorio);
    if (filters.osc) qs.set("osc", filters.osc);
    if (filters.papel) qs.set("papel", filters.papel);
    if (filters.ativo) qs.set("ativo", filters.ativo);
    if (limit !== DEFAULT_LIMIT) qs.set("limit", String(limit));
    if (offset > 0) qs.set("offset", String(offset));
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [filters, limit, offset, pathname, router]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchTerritoryOptions(controller.signal).catch(() => [] as SelectOption[]),
      fetchOscOptions(controller.signal),
      fetchUserOptions(controller.signal),
    ]).then(([territorios, oscs, users]) => {
      if (controller.signal.aborted) return;
      setTerritorioOptions(territorios);
      setOscOptions(oscs);
      setUserOptions(users);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setDataLoading(true);
    setError(null);
    listTecnicosSGP(
      {
        limit,
        offset,
        territorio: filters.territorio || undefined,
        osc: filters.osc || undefined,
        papel: filters.papel || undefined,
        ativo: filters.ativo || undefined,
      },
      controller.signal,
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        setTecnicos(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar os técnicos.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });
    return () => controller.abort();
  }, [limit, offset, filters, reloadKey]);

  const handleFilterChange = useCallback(
    (patch: Partial<TecnicosFiltersValue>) => {
      setFilters((prev) => ({ ...prev, ...patch }));
      setOffset(0);
    },
    [],
  );

  const handleRowClick = useCallback(
    (t: TecnicoListItem) => {
      setSlideOver({
        open: true,
        mode: canWrite ? "edit" : "view",
        tecnico: t,
      });
    },
    [canWrite],
  );

  const handleSaved = useCallback((saved: TecnicoListItem) => {
    setSlideOver({ open: false, mode: "view" });
    setReloadKey((k) => k + 1);
  }, []);

  const handleDeactivated = useCallback((id: number) => {
    setSlideOver({ open: false, mode: "view" });
    setTecnicos((prev) =>
      prev.map((t) => (t.id === id ? { ...t, ativo: false } : t)),
    );
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGP", href: "/sgp" },
          { label: "Técnicos" },
        ]}
      />

      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Técnicos
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Cadastro de técnicos por território e OSC.
          </p>
        </div>
        {canWrite && (
          <Button
            onClick={() =>
              setSlideOver({ open: true, mode: "create" })
            }
          >
            Adicionar técnico
          </Button>
        )}
      </div>

      <TecnicosFilters
        filters={filters}
        territorioOptions={territorioOptions}
        oscOptions={oscOptions}
        onChange={handleFilterChange}
        onClear={() => {
          setFilters(EMPTY_FILTERS);
          setOffset(0);
        }}
      />

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
      ) : tecnicos.length === 0 ? (
        <EmptyState
          icon={<SearchX className="h-8 w-8" />}
          title={
            hasActiveFilters
              ? "Nenhum técnico encontrado"
              : "Nenhum técnico cadastrado"
          }
          description={
            hasActiveFilters
              ? "Tente ajustar os filtros."
              : canWrite
                ? "Adicione o primeiro técnico para começar."
                : "Nenhum técnico disponível no momento."
          }
          action={
            hasActiveFilters ? (
              <Button
                variant="secondary"
                onClick={() => {
                  setFilters(EMPTY_FILTERS);
                  setOffset(0);
                }}
              >
                Limpar filtros
              </Button>
            ) : canWrite ? (
              <Button
                onClick={() => setSlideOver({ open: true, mode: "create" })}
              >
                Adicionar técnico
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <TecnicosTable tecnicos={tecnicos} onSelect={handleRowClick} />
          {count > limit && (
            <Pagination
              count={count}
              limit={limit}
              offset={offset}
              pageSizes={PAGE_SIZES}
              onOffsetChange={setOffset}
              onLimitChange={(l) => {
                setLimit(l);
                setOffset(0);
              }}
            />
          )}
        </>
      )}

      <TecnicoSlideOver
        open={slideOver.open}
        onClose={() => setSlideOver((s) => ({ ...s, open: false }))}
        mode={slideOver.mode}
        tecnico={slideOver.tecnico}
        userOptions={userOptions}
        territorioOptions={territorioOptions}
        oscOptions={oscOptions}
        onSaved={handleSaved}
        onDeactivated={handleDeactivated}
      />
    </div>
  );
}

export default function TecnicosPage() {
  return (
    <>
      <PageHeader>
        <div className="flex items-center gap-2">
          <UserCog className="h-5 w-5 text-text-muted" />
          <span className="truncate text-base font-semibold text-text">
            Técnicos
          </span>
        </div>
      </PageHeader>
      <Suspense fallback={<CenteredSpinner />}>
        <TecnicosView />
      </Suspense>
    </>
  );
}
