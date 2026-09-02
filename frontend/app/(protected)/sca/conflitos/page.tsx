"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, GitCompareArrows, SearchX } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { useCanReviewSyncConflicts } from "@/app/lib/auth/roles";
import {
  CONFLITOS_POR_PAGINA,
  listConflitos,
  type Conflito,
} from "@/app/lib/conflitos";
import {
  ConflitoFilters,
  ENTIDADES_VALIDAS,
  FILTROS_VAZIOS,
  SENSIVEL_VALIDOS,
  STATUS_VALIDOS,
  type ConflitoFiltersValue,
} from "./_components/ConflitoFilters";
import { ConflitosTable } from "./_components/ConflitosTable";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function ConflitosConteudo() {
  const { loading: authLoading, canReview } = useCanReviewSyncConflicts();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [conflitos, setConflitos] = useState<Conflito[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // ── Filtros e página: a URL é o estado ────────────────────────────────────
  // Mesmo padrão do Painel de Acompanhamento — o recorte sobrevive ao refresh e
  // pode ser compartilhado por link. Valores fora do vocabulário do backend são
  // ignorados na leitura: a URL é digitável e um valor inválido devolveria 400.
  const filtros: ConflitoFiltersValue = useMemo(() => {
    const validar = (chave: string, aceitos: string[]) => {
      const bruto = searchParams.get(chave) ?? "";
      return aceitos.includes(bruto) ? bruto : "";
    };
    return {
      status: validar("status", STATUS_VALIDOS),
      sensivel: validar("sensivel", SENSIVEL_VALIDOS),
      entidade: validar("entidade", ENTIDADES_VALIDAS),
    };
  }, [searchParams]);

  const offset = useMemo(() => {
    const bruto = searchParams.get("offset") ?? "";
    return /^\d+$/.test(bruto) ? Number(bruto) : 0;
  }, [searchParams]);

  const escrever = useCallback(
    (proximos: ConflitoFiltersValue, proximoOffset: number) => {
      const qs = new URLSearchParams();
      for (const [chave, valor] of Object.entries(proximos)) {
        if (valor) qs.set(chave, valor);
      }
      if (proximoOffset > 0) qs.set("offset", String(proximoOffset));
      const query = qs.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [router, pathname],
  );

  // Mexer num filtro volta para a primeira página: manter o offset mostraria
  // uma página vazia sempre que o novo recorte tiver menos itens.
  const patchFiltros = useCallback(
    (patch: Partial<ConflitoFiltersValue>) =>
      escrever({ ...filtros, ...patch }, 0),
    [escrever, filtros],
  );

  const limparFiltros = useCallback(
    () => escrever(FILTROS_VAZIOS, 0),
    [escrever],
  );

  const irParaOffset = useCallback(
    (proximo: number) => escrever(filtros, proximo),
    [escrever, filtros],
  );

  useEffect(() => {
    if (!canReview) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listConflitos(
      {
        status: filtros.status,
        campo_sensivel: filtros.sensivel,
        entidade: filtros.entidade,
      },
      offset,
      controller.signal,
    )
      .then((res) => {
        setConflitos(res.results);
        setTotal(res.count);
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
            : "Não foi possível carregar os conflitos. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [
    canReview,
    filtros.status,
    filtros.sensivel,
    filtros.entidade,
    offset,
    reloadKey,
  ]);

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Conflitos de sincronização
      </h1>
    </PageHeader>
  );

  if (authLoading) {
    return (
      <>
        {header}
        <CenteredSpinner />
      </>
    );
  }

  if (!canReview || forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const temFiltro =
    filtros.status !== "" || filtros.sensivel !== "" || filtros.entidade !== "";
  const primeiraCarga = loading && conflitos === null;
  const semResultado = !loading && !error && (conflitos?.length ?? 0) === 0;

  return (
    <div data-testid="conflitos-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "Conflitos de sincronização" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          Divergências entre o que foi coletado em campo e o que está no
          servidor. Campos sensíveis — nome, CPF e coordenadas — ficam pendentes
          e exigem decisão de uma pessoa; os demais o sistema já resolveu
          sozinho. Você vê os conflitos dos territórios sob sua responsabilidade.
        </p>

        <ConflitoFilters
          value={filtros}
          onChange={patchFiltros}
          onClear={limparFiltros}
        />

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)}>
              Tentar novamente
            </Button>
          </div>
        ) : primeiraCarga ? (
          <CenteredSpinner />
        ) : semResultado && !temFiltro ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<GitCompareArrows className="h-7 w-7" />}
              title="Nenhum conflito registrado"
              description="Quando uma sincronização do aplicativo de campo divergir do servidor, o conflito aparece aqui."
            />
          </div>
        ) : semResultado ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<SearchX className="h-7 w-7" />}
              title="Nenhum conflito corresponde aos filtros"
              description="Ajuste o status, a sensibilidade ou a entidade para ver os conflitos registrados."
              action={
                <Button variant="secondary" onClick={limparFiltros}>
                  Limpar filtros
                </Button>
              }
            />
          </div>
        ) : (
          <div
            aria-busy={loading}
            className={`flex flex-col gap-4 transition-opacity ${
              loading ? "opacity-60" : ""
            }`}
          >
            <ConflitosTable conflitos={conflitos ?? []} />

            {total > CONFLITOS_POR_PAGINA && (
              <Pagination
                count={total}
                offset={offset}
                limit={CONFLITOS_POR_PAGINA}
                onOffsetChange={irParaOffset}
                // O tamanho da página é fixo: sem seletor, a paginação não
                // precisa negociar limite com a URL.
                onLimitChange={() => {}}
                pageSizes={[CONFLITOS_POR_PAGINA]}
                itemNoun={{ one: "conflito", other: "conflitos" }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** `useSearchParams` exige um limite de Suspense acima — como nas demais telas. */
export default function ConflitosPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <ConflitosConteudo />
    </Suspense>
  );
}
