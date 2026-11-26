"use client";

import { Suspense, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import { canRemanejarOrcamento, canVerHistoricoRemanejamentos } from "@/app/lib/auth/roles";
import { RUBRICAS, RUBRICA_SLUGS } from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";
import { TRANSFERENCIAS_POR_PAGINA, listTransferencias } from "@/app/lib/remanejamentos";
import { HistoricoTabela } from "./_components/HistoricoTabela";

const PAGE_SIZES = [TRANSFERENCIAS_POR_PAGINA, 50, 100];

const OPCOES_RUBRICA: SelectOption[] = [
  { value: "", label: "Todas as rubricas" },
  ...RUBRICAS.map((r) => ({ value: r.slug, label: r.nome })),
];

function Carregando() {
  return (
    <div
      role="status"
      className="flex min-h-[30vh] items-center justify-center gap-2 text-sm text-text-muted"
    >
      <Spinner className="h-5 w-5 animate-spin" />
      Carregando remanejamentos…
    </div>
  );
}

/**
 * Histórico de remanejamentos (#466, SGP-RF41): os remanejamentos efetivados,
 * diretos da UGP, de excedente autorizado na demanda e de recurso extra, do
 * mais recente ao mais antigo. Lê `GET /api/v1/sgd/remanejamentos/transferencias/`.
 *
 * Só o filtro por rubrica: território, período, responsável, documento de
 * respaldo e exportação CSV esperam o backend
 * (pendencias-backend-sprint-12h.md, item 2).
 */
function HistoricoRemanejamentos() {
  const { data: session, status: sessao } = useSession();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const pode = canVerHistoricoRemanejamentos(session?.user);

  const filtros = useMemo(() => {
    const rubrica = searchParams.get("rubrica") ?? "";
    const limite = Number(searchParams.get("limit"));
    const deslocamento = Number(searchParams.get("offset"));
    return {
      rubrica: RUBRICA_SLUGS.includes(rubrica) ? rubrica : undefined,
      limit: PAGE_SIZES.includes(limite) ? limite : TRANSFERENCIAS_POR_PAGINA,
      offset: Number.isInteger(deslocamento) && deslocamento > 0 ? deslocamento : 0,
    };
  }, [searchParams]);

  const lista = useQuery({
    queryKey: qk.remanejamentos.historico(filtros),
    queryFn: ({ signal }) => listTransferencias(filtros, signal),
    enabled: pode,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  const transferencias = lista.data?.transferencias ?? [];
  const total = lista.data?.total ?? 0;

  function navegar(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  // Link antigo ou página que deixou de existir: volta à última que existe.
  const alemDoFim =
    lista.isSuccess && !lista.isPlaceholderData && filtros.offset > 0 && filtros.offset >= total;
  useEffect(() => {
    if (!alemDoFim) return;
    const ultima = total > 0 ? Math.floor((total - 1) / filtros.limit) * filtros.limit : 0;
    const next = new URLSearchParams(searchParams.toString());
    if (ultima > 0) next.set("offset", String(ultima));
    else next.delete("offset");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [alemDoFim, total, filtros.limit, searchParams, router, pathname]);

  if (sessao === "loading") return <Carregando />;
  if (!pode) {
    return (
      <RestrictedAccess description="O histórico de remanejamentos é da UGP e do Super Admin, que remanejam, e da FGD, que acompanha." />
    );
  }

  const erro =
    lista.error instanceof ApiError
      ? lista.error.message
      : lista.error
        ? "Não foi possível carregar os remanejamentos."
        : null;

  return (
    <div className="flex flex-col gap-5">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGP", href: "/sgp" },
          { label: "Orçamento", href: "/sgp/orcamento" },
          { label: "Remanejamentos" },
        ]}
      />
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Histórico de remanejamentos</h1>
          <p className="mt-1 max-w-prose text-sm text-text-muted">
            Os remanejamentos efetivados entre pools: os feitos direto pela UGP, os excedentes
            autorizados nas demandas e os que cobriram um pedido de recurso extra, com o saldo dos
            dois pools antes e depois.
          </p>
        </div>
        {canRemanejarOrcamento(session?.user) && (
          <Button as="a" size="sm" href="/sgp/orcamento/remanejamentos/novo" data-testid="historico-ir-remanejar">
            Remanejar
          </Button>
        )}
      </header>

      <div
        className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4"
        data-testid="historico-filtros"
      >
        <Select
          id="historico-filtro-rubrica"
          label="Rubrica"
          className="w-full sm:w-64"
          options={OPCOES_RUBRICA}
          value={filtros.rubrica ?? ""}
          onChange={(v) => navegar({ rubrica: v || null, offset: null })}
          placeholder="Todas as rubricas"
        />
      </div>

      {lista.isPending ? (
        <Carregando />
      ) : erro ? (
        <TabErroSection message={erro} onRetry={() => void lista.refetch()} />
      ) : transferencias.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState
            icon={<Scale className="h-7 w-7" />}
            title={filtros.rubrica ? "Nenhum remanejamento nesta rubrica" : "Nenhum remanejamento efetivado"}
            description={
              filtros.rubrica
                ? "Escolha outra rubrica ou veja todas."
                : "Os remanejamentos feitos pelo Remanejar, os excedentes autorizados nas demandas e os pedidos de recurso extra aprovados aparecem aqui."
            }
          />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <HistoricoTabela transferencias={transferencias} />
          <Pagination
            count={total}
            offset={filtros.offset}
            limit={filtros.limit}
            pageSizes={PAGE_SIZES}
            onOffsetChange={(offset) => navegar({ offset: offset > 0 ? String(offset) : null })}
            onLimitChange={(limit) =>
              navegar({ limit: limit === TRANSFERENCIAS_POR_PAGINA ? null : String(limit), offset: null })
            }
            itemNoun={{ one: "remanejamento", other: "remanejamentos" }}
          />
        </div>
      )}
    </div>
  );
}

export default function HistoricoRemanejamentosPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">Histórico de remanejamentos</span>
      </PageHeader>
      <Suspense fallback={<Carregando />}>
        <HistoricoRemanejamentos />
      </Suspense>
    </>
  );
}
