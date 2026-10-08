"use client";

import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { ApiError } from "@/app/lib/api";
import { listDemandas } from "@/app/lib/demandas";
import { useFilaDemandas } from "@/app/lib/hooks/useFilaDemandas";
import { qk } from "@/app/lib/queryKeys";
import { DemandaPainel } from "./_components/DemandaPainel";
import { DemandasTabela } from "./_components/DemandasTabela";

type Visao = "minha" | "todas";

function Carregando() {
  return (
    <div
      role="status"
      className="flex min-h-[30vh] items-center justify-center gap-2 text-sm text-text-muted"
    >
      <Spinner className="h-5 w-5 animate-spin" />
      Carregando demandas…
    </div>
  );
}

function PainelDemandasView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const fila = useFilaDemandas();
  const visao: Visao =
    searchParams.get("visao") === "todas" || !fila.decide ? "todas" : "minha";
  const bruto = searchParams.get("demanda") ?? "";
  const selecionada = /^\d+$/.test(bruto) ? Number(bruto) : null;

  const todas = useQuery({
    queryKey: qk.demandas.lista([]),
    queryFn: ({ signal }) => listDemandas({}, signal),
    enabled: visao === "todas",
    staleTime: 30_000,
  });
  const atual = visao === "minha" ? fila : todas;
  const demandas = atual.data ?? [];

  function navegar(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const erro =
    atual.error instanceof ApiError
      ? atual.error.message
      : atual.error
        ? "Não foi possível carregar as demandas."
        : null;

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGD", href: "/sgd" },
          { label: "Demandas" },
        ]}
      />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Demandas</h1>
          <p className="mt-1 text-sm text-text-muted">
            Pedidos de recurso das atividades, com o fluxo de decisão de cada perfil.
          </p>
        </div>

        {fila.decide && (
          <div
            role="tablist"
            aria-label="Visão das demandas"
            className="inline-flex rounded-md border border-border bg-surface p-0.5"
          >
            {(
              [
                ["minha", `Aguardando minha ação${fila.total !== undefined ? ` (${fila.total})` : ""}`],
                ["todas", "Todas"],
              ] as const
            ).map(([valor, rotulo]) => (
              <button
                key={valor}
                type="button"
                role="tab"
                aria-selected={visao === valor}
                onClick={() => navegar({ visao: valor === "minha" ? null : "todas", demanda: null })}
                className={`rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                  visao === valor ? "bg-primary text-surface" : "text-text-muted hover:text-text"
                }`}
                data-testid={`demandas-visao-${valor}`}
              >
                {rotulo}
              </button>
            ))}
          </div>
        )}
      </div>

      <div
        className={`grid items-start gap-5 ${
          selecionada !== null ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]" : ""
        }`}
      >
        <div className="min-w-0">
          {atual.isPending ? (
            <Carregando />
          ) : erro ? (
            <TabErroSection message={erro} onRetry={() => void atual.refetch()} />
          ) : demandas.length === 0 ? (
            <div className="rounded-lg border border-border bg-surface">
              <EmptyState
                icon={<Inbox className="h-7 w-7" />}
                title={
                  visao === "minha"
                    ? "Nenhuma demanda aguardando a sua ação"
                    : "Nenhuma demanda por aqui"
                }
                description={
                  visao === "minha"
                    ? "Quando uma demanda chegar à sua etapa de decisão, ela aparece aqui."
                    : "As demandas visíveis para o seu perfil aparecem aqui."
                }
              />
            </div>
          ) : (
            <DemandasTabela
              demandas={demandas}
              selecionada={selecionada}
              compacta={selecionada !== null}
              onSelecionar={(id) => navegar({ demanda: String(id) })}
            />
          )}
        </div>

        {selecionada !== null && (
          <DemandaPainel
            key={selecionada}
            demandaId={selecionada}
            onFechar={() => navegar({ demanda: null })}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Painel master-detail de Demandas (#296, SGD-RF18 a RF23) — a tela de
 * trabalho do Articulador Estadual, da UGP e da FGD.
 */
export default function PainelDemandasPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>
      <Suspense fallback={<Carregando />}>
        <PainelDemandasView />
      </Suspense>
    </>
  );
}
