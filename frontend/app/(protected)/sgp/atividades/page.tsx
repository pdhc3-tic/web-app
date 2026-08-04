"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, ClipboardList, Plus, SearchX } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import Spinner from "@/app/components/icons/Spinner";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import {
  FALLBACK_CHOICES,
  fetchAtividadeChoices,
  listAcoes,
  listAtividades,
  listTecnicos,
  type AcaoPT,
  type AtividadeChoices,
  type AtividadeListItem,
} from "@/app/lib/atividades";
import { fetchProjetoOptions, fetchTerritoryOptions } from "@/app/lib/upfs";
import {
  AtividadesFilters,
  EMPTY_FILTERS,
  type AtividadesFiltersValue,
} from "./_components/AtividadesFilters";
import { AtividadesTable } from "./_components/AtividadesTable";

const DEFAULT_LIMIT = 20; // espelha ActivityPagination.page_size
const PAGE_SIZES = [20, 50, 100];

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function AtividadesView() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const [filters, setFilters] = useState<AtividadesFiltersValue>(() => ({
    acao: searchParams.get("acao") ?? "",
    projeto: searchParams.get("projeto") ?? "",
    territorio: searchParams.get("territorio") ?? "",
    tecnico: searchParams.get("tecnico") ?? "",
    tipo: searchParams.get("tipo") ?? "",
    status: searchParams.get("status") ?? "",
    inicioDe: searchParams.get("de") ?? "",
    inicioAte: searchParams.get("ate") ?? "",
  }));
  const [limit, setLimit] = useState<number>(() => {
    const l = Number(searchParams.get("limit"));
    return PAGE_SIZES.includes(l) ? l : DEFAULT_LIMIT;
  });
  const [offset, setOffset] = useState<number>(() => {
    const o = Number(searchParams.get("offset"));
    return Number.isFinite(o) && o > 0 ? o : 0;
  });

  const [atividades, setAtividades] = useState<AtividadeListItem[]>([]);
  const [count, setCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [acoes, setAcoes] = useState<AcaoPT[]>([]);
  const [projetoOptions, setProjetoOptions] = useState<SelectOption[]>([]);
  const [territorioOptions, setTerritorioOptions] = useState<SelectOption[]>([]);
  const [tecnicoOptions, setTecnicoOptions] = useState<SelectOption[]>([]);
  const [choices, setChoices] = useState<AtividadeChoices>(FALLBACK_CHOICES);
  const [optionsLoading, setOptionsLoading] = useState(true);

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some((v) => v !== ""),
    [filters],
  );

  // ── Sincroniza os filtros com a query string ─────────────────────────────
  useEffect(() => {
    const qs = new URLSearchParams();
    if (filters.acao) qs.set("acao", filters.acao);
    if (filters.projeto) qs.set("projeto", filters.projeto);
    if (filters.territorio) qs.set("territorio", filters.territorio);
    if (filters.tecnico) qs.set("tecnico", filters.tecnico);
    if (filters.tipo) qs.set("tipo", filters.tipo);
    if (filters.status) qs.set("status", filters.status);
    if (filters.inicioDe) qs.set("de", filters.inicioDe);
    if (filters.inicioAte) qs.set("ate", filters.inicioAte);
    if (limit !== DEFAULT_LIMIT) qs.set("limit", String(limit));
    if (offset > 0) qs.set("offset", String(offset));
    const query = qs.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [filters, limit, offset, pathname, router]);

  // ── Opções dos filtros ───────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOptionsLoading(true);
    Promise.all([
      listAcoes(controller.signal).catch(() => [] as AcaoPT[]),
      fetchProjetoOptions(controller.signal),
      fetchTerritoryOptions(controller.signal).catch(() => [] as SelectOption[]),
      listTecnicos(controller.signal),
      fetchAtividadeChoices(controller.signal),
    ])
      .then(([acoesData, projetos, territorios, tecnicos, choicesData]) => {
        if (controller.signal.aborted) return;
        setAcoes(acoesData);
        setProjetoOptions(projetos);
        setTerritorioOptions(territorios);
        setTecnicoOptions(
          tecnicos.map((t) => ({ value: String(t.id), label: t.nome })),
        );
        setChoices(choicesData);
      })
      .finally(() => {
        if (!controller.signal.aborted) setOptionsLoading(false);
      });
    return () => controller.abort();
  }, []);

  // ── Listagem ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listAtividades(
      {
        limit,
        offset,
        acao: filters.acao || undefined,
        projeto: filters.projeto || undefined,
        territorio: filters.territorio || undefined,
        tecnico: filters.tecnico || undefined,
        tipo: filters.tipo || undefined,
        status: filters.status || undefined,
        inicioDe: filters.inicioDe || undefined,
        inicioAte: filters.inicioAte || undefined,
      },
      controller.signal,
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        setAtividades(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as atividades. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [limit, offset, filters, reloadKey]);

  // A query string guarda só o id da ação; o combobox precisa do objeto.
  // Até `listAcoes` responder, o campo aparece vazio — e um id órfão (ação fora
  // do escopo do usuário) simplesmente não seleciona nada.
  const acaoSelecionada = useMemo(
    () => acoes.find((a) => String(a.id) === filters.acao) ?? null,
    [acoes, filters.acao],
  );

  const handleFilterChange = useCallback(
    (patch: Partial<AtividadesFiltersValue>) => {
      setFilters((prev) => ({ ...prev, ...patch }));
      // Sem isto o usuário fica numa página que deixou de existir depois do
      // filtro e vê uma lista vazia enganosa.
      setOffset(0);
    },
    [],
  );

  const handleClearFilters = useCallback(() => {
    setFilters(EMPTY_FILTERS);
    setOffset(0);
  }, []);

  const handleLimitChange = useCallback((newLimit: number) => {
    setLimit(newLimit);
    setOffset(0);
  }, []);

  const handleNovaAtividade = useCallback(() => {
    router.push("/sgp/atividades/nova/");
  }, [router]);

  const showEmpty = !dataLoading && !error && atividades.length === 0;

  return (
    <>
      <PageHeader>
        <div className="flex w-full items-center justify-between gap-3">
          <h1 className="truncate text-base font-semibold text-text">
            Atividades
          </h1>
          <Button
            size="sm"
            onClick={handleNovaAtividade}
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
            { label: "Atividades" },
          ]}
        />

        <AtividadesFilters
          value={filters}
          onChange={handleFilterChange}
          onClear={handleClearFilters}
          hasActiveFilters={hasActiveFilters}
          acoes={acoes}
          acaoSelecionada={acaoSelecionada}
          choices={choices}
          projetoOptions={projetoOptions}
          territorioOptions={territorioOptions}
          tecnicoOptions={tecnicoOptions}
          optionsLoading={optionsLoading}
        />

        {/* Os skeletons da tabela seguram o layout para quem vê; este status é
            o que anuncia o carregamento para quem usa leitor de tela. */}
        {dataLoading && (
          <p role="status" className="sr-only">
            Carregando atividades…
          </p>
        )}

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
                title="Nenhuma atividade neste período."
                description="Nenhuma atividade corresponde aos filtros aplicados. Tente ajustá-los ou limpar tudo."
                action={
                  <Button variant="secondary" onClick={handleClearFilters}>
                    Limpar filtros
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={<ClipboardList className="h-7 w-7" />}
                title="Nenhuma atividade neste período."
                description="Comece registrando a primeira atividade de campo."
                action={
                  <Button
                    variant="primary"
                    onClick={handleNovaAtividade}
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    Nova atividade
                  </Button>
                }
              />
            )}
          </div>
        ) : (
          <>
            <AtividadesTable atividades={atividades} loading={dataLoading} />
            {count > 0 && (
              <Pagination
                count={count}
                offset={offset}
                limit={limit}
                onOffsetChange={setOffset}
                onLimitChange={handleLimitChange}
                pageSizes={PAGE_SIZES}
                itemNoun={{ one: "atividade", other: "atividades" }}
              />
            )}
          </>
        )}
      </div>
    </>
  );
}

export default function AtividadesPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <AtividadesView />
    </Suspense>
  );
}
