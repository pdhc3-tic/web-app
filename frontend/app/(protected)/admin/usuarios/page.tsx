"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { UserPlus, AlertTriangle, SearchX, Users } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import Spinner from "@/app/components/icons/Spinner";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import {
  listUsers,
  fetchRoleOptions,
  fetchTerritoryOptions,
  type StatusFilter,
  type UserListItem,
} from "@/app/lib/users";
import { ApiError } from "@/app/lib/api";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { UsersFilters, type UsersFiltersValue } from "./_components/UsersFilters";
import { UsersTable } from "./_components/UsersTable";

const SEARCH_DEBOUNCE_MS = 300;
const DEFAULT_LIMIT = 25;
const PAGE_SIZES = [25, 50, 100];

const DEFAULT_FILTERS: UsersFiltersValue = {
  search: "",
  perfil: "",
  territorio: "",
  status: "ativos",
  ultimoAcessoDe: "",
  ultimoAcessoAte: "",
};

function parseStatus(value: string | null): StatusFilter {
  return value === "inativos" || value === "todos" ? value : "ativos";
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function UsuariosView() {
  const { loading: authLoading, isSuperAdmin } = useIsSuperAdmin();

  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const [filters, setFilters] = useState<UsersFiltersValue>(() => ({
    search: searchParams.get("q") ?? "",
    perfil: searchParams.get("perfil") ?? "",
    territorio: searchParams.get("territorio") ?? "",
    status: parseStatus(searchParams.get("status")),
    ultimoAcessoDe: searchParams.get("de") ?? "",
    ultimoAcessoAte: searchParams.get("ate") ?? "",
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
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newUserOpen, setNewUserOpen] = useState(false);

  const [users, setUsers] = useState<UserListItem[]>([]);
  const [count, setCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [roleOptions, setRoleOptions] = useState<SelectOption[]>([]);
  const [territoryOptions, setTerritoryOptions] = useState<SelectOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);

  const hasActiveFilters = useMemo(() => {
    return (
      filters.search.trim() !== "" ||
      filters.perfil !== "" ||
      filters.territorio !== "" ||
      filters.status !== DEFAULT_FILTERS.status ||
      filters.ultimoAcessoDe !== "" ||
      filters.ultimoAcessoAte !== ""
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
    if (filters.perfil) qs.set("perfil", filters.perfil);
    if (filters.territorio) qs.set("territorio", filters.territorio);
    if (filters.status !== "ativos") qs.set("status", filters.status);
    if (filters.ultimoAcessoDe) qs.set("de", filters.ultimoAcessoDe);
    if (filters.ultimoAcessoAte) qs.set("ate", filters.ultimoAcessoAte);
    if (limit !== DEFAULT_LIMIT) qs.set("limit", String(limit));
    if (offset > 0) qs.set("offset", String(offset));
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
  }, [
    debouncedSearch,
    filters.perfil,
    filters.territorio,
    filters.status,
    filters.ultimoAcessoDe,
    filters.ultimoAcessoAte,
    limit,
    offset,
    pathname,
    router,
  ]);

  useEffect(() => {
    if (!isSuperAdmin) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOptionsLoading(true);
    Promise.all([
      fetchRoleOptions(controller.signal),
      fetchTerritoryOptions(controller.signal),
    ])
      .then(([roles, territories]) => {
        setRoleOptions(roles);
        setTerritoryOptions(territories);
      })
      .catch(() => {
        /* filtros seguem vazios; a listagem ainda funciona */
      })
      .finally(() => setOptionsLoading(false));
    return () => controller.abort();
  }, [isSuperAdmin]);

  useEffect(() => {
    if (!isSuperAdmin) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listUsers(
      {
        limit,
        offset,
        search: debouncedSearch,
        perfil: filters.perfil || undefined,
        territorio: filters.territorio || undefined,
        status: filters.status,
        ultimoAcessoDe: filters.ultimoAcessoDe || undefined,
        ultimoAcessoAte: filters.ultimoAcessoAte || undefined,
        ordering: "-ultimo_login",
      },
      controller.signal,
    )
      .then((data) => {
        setUsers(data.results);
        setCount(data.count);
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
            : "Não foi possível carregar os usuários. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [
    isSuperAdmin,
    limit,
    offset,
    debouncedSearch,
    filters.perfil,
    filters.territorio,
    filters.status,
    filters.ultimoAcessoDe,
    filters.ultimoAcessoAte,
    reloadKey,
  ]);

  const handleFilterChange = useCallback(
    (patch: Partial<UsersFiltersValue>) => {
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

  const handleNewUser = useCallback(() => {
    setNewUserOpen(true);
  }, []);

  const handleSelect = useCallback((user: UserListItem) => {
    setSelectedId((prev) => (prev === user.id ? null : user.id));
  }, []);

  if (authLoading) {
    return <CenteredSpinner />;
  }

  if (!isSuperAdmin || forbidden) {
    return (
      <>
        <PageHeader>
          <h1 className="truncate text-base font-semibold text-text">
            Usuários
          </h1>
        </PageHeader>
        <RestrictedAccess />
      </>
    );
  }

  const showEmpty = !dataLoading && !error && users.length === 0;

  return (
    <>
      <PageHeader>
        <div className="flex w-full items-center justify-between gap-3">
          <h1 className="truncate text-base font-semibold text-text">
            Usuários
          </h1>
          <Button
            size="sm"
            onClick={handleNewUser}
            leftIcon={<UserPlus className="h-4 w-4" />}
          >
            Novo usuário
          </Button>
        </div>
      </PageHeader>

      <div className="flex flex-col gap-4">
        <UsersFilters
          value={filters}
          onChange={handleFilterChange}
          onClear={handleClearFilters}
          hasActiveFilters={hasActiveFilters}
          roleOptions={roleOptions}
          territoryOptions={territoryOptions}
          optionsLoading={optionsLoading}
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
        ) : showEmpty ? (
          <div className="rounded-lg border border-border bg-surface">
            {hasActiveFilters ? (
              <EmptyState
                icon={<SearchX className="h-7 w-7" />}
                title="Nenhum resultado"
                description="Não encontramos usuários com os filtros aplicados. Tente ajustar ou limpar os filtros."
                action={
                  <Button variant="secondary" onClick={handleClearFilters}>
                    Limpar filtros
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={<Users className="h-7 w-7" />}
                title="Nenhum usuário cadastrado"
                description="Ainda não há usuários no sistema. Comece cadastrando o primeiro."
                action={
                  <Button
                    variant="primary"
                    onClick={handleNewUser}
                    leftIcon={<UserPlus className="h-4 w-4" />}
                  >
                    Novo usuário
                  </Button>
                }
              />
            )}
          </div>
        ) : (
          <>
            <UsersTable
              users={users}
              selectedId={selectedId}
              onSelect={handleSelect}
              loading={dataLoading}
            />
            <Pagination
              count={count}
              offset={offset}
              limit={limit}
              onOffsetChange={setOffset}
              onLimitChange={handleLimitChange}
              itemNoun={{ one: "usuário", other: "usuários" }}
            />
          </>
        )}
      </div>

      <SlideOver
        open={newUserOpen}
        onClose={() => setNewUserOpen(false)}
        title="Novo usuário"
      >
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-text-muted">
            <UserPlus className="h-6 w-6" />
          </span>
          <p className="max-w-xs text-sm leading-relaxed text-text-muted">
            O formulário de cadastro de usuário será implementado na próxima
            sprint.
          </p>
        </div>
      </SlideOver>
    </>
  );
}

export default function UsuariosPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <UsuariosView />
    </Suspense>
  );
}
