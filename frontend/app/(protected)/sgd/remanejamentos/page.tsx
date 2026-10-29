"use client";

import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import {
  canAcessarFilaRemanejamentos,
  canDecidirRemanejamento,
  canEmitirParecerRemanejamento,
} from "@/app/lib/auth/roles";
import { listPedidos, type StatusPedido } from "@/app/lib/remanejamentos";
import { qk } from "@/app/lib/queryKeys";
import { PedidosTabela } from "./_components/PedidosTabela";

type Visao = "minha" | "todos";

function Carregando() {
  return (
    <div
      role="status"
      className="flex min-h-[30vh] items-center justify-center gap-2 text-sm text-text-muted"
    >
      <Spinner className="h-5 w-5 animate-spin" />
      Carregando pedidos…
    </div>
  );
}

function FilaRemanejamentosView() {
  const { data: session, status: sessao } = useSession();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const user = session?.user;
  const visao: Visao = searchParams.get("visao") === "todos" ? "todos" : "minha";

  // A etapa de cada perfil: o Articulador emite parecer nos Submetidos; a UGP
  // decide os Com parecer. O Super Admin faz as duas.
  const daMinhaEtapa: StatusPedido[] = [
    ...(canEmitirParecerRemanejamento(user) ? (["submetida"] as const) : []),
    ...(canDecidirRemanejamento(user) ? (["com_parecer"] as const) : []),
  ];
  const status = visao === "todos" ? (["todos"] as const) : daMinhaEtapa;

  const lista = useQuery({
    queryKey: qk.remanejamentos.lista(status),
    queryFn: ({ signal }) => listPedidos({ status: [...status] }, signal),
    enabled: canAcessarFilaRemanejamentos(user),
    staleTime: 30_000,
  });

  if (sessao === "loading") return <Carregando />;
  if (!canAcessarFilaRemanejamentos(user)) {
    return (
      <RestrictedAccess description="A Fila de Remanejamentos é da UGP, que decide os pedidos de recurso extra, e do Articulador Estadual, que emite o parecer." />
    );
  }

  const erro =
    lista.error instanceof ApiError
      ? lista.error.message
      : lista.error
        ? "Não foi possível carregar os pedidos."
        : null;
  const pedidos = lista.data?.pedidos ?? [];

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Fila de Remanejamentos</h1>
          <p className="mt-1 text-sm text-text-muted">
            Pedidos de recurso extra das demandas bloqueadas pelo limite individual.
          </p>
        </div>

        <div
          role="tablist"
          aria-label="Visão dos pedidos"
          className="inline-flex rounded-md border border-border bg-surface p-0.5"
        >
          {(
            [
              ["minha", "Aguardando minha ação"],
              ["todos", "Todos"],
            ] as const
          ).map(([valor, rotulo]) => (
            <button
              key={valor}
              type="button"
              role="tab"
              aria-selected={visao === valor}
              onClick={() =>
                router.push(valor === "todos" ? `${pathname}?visao=todos` : pathname, { scroll: false })
              }
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                visao === valor ? "bg-primary text-surface" : "text-text-muted hover:text-text"
              }`}
              data-testid={`remanejamentos-visao-${valor}`}
            >
              {rotulo}
            </button>
          ))}
        </div>
      </div>

      {lista.isPending ? (
        <Carregando />
      ) : erro ? (
        <TabErroSection message={erro} onRetry={() => void lista.refetch()} />
      ) : pedidos.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState
            icon={<Scale className="h-7 w-7" />}
            title={visao === "minha" ? "Nenhum pedido aguardando a sua ação" : "Nenhum pedido por aqui"}
            description={
              visao === "minha"
                ? "Quando um pedido de recurso extra chegar à sua etapa, ele aparece aqui."
                : "Os pedidos de recurso extra visíveis para o seu perfil aparecem aqui."
            }
          />
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <PedidosTabela pedidos={pedidos} />
          {lista.data && lista.data.total > pedidos.length && (
            <p role="status" className="text-xs text-text-muted" data-testid="remanejamentos-lista-parcial">
              Mostrando {pedidos.length} de {lista.data.total} pedidos.
            </p>
          )}
        </div>
      )}
    </>
  );
}

/**
 * Fila de Remanejamentos (#321 · SGD-FE-10): os pedidos de recurso extra das
 * demandas bloqueadas pelo limite individual, com o parecer do Articulador
 * Estadual e a decisão da UGP. Cada pedido abre em `/sgd/remanejamentos/{id}`,
 * o link que as notificações do backend usam.
 */
export default function FilaRemanejamentosPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>
      <div className="mx-auto flex max-w-6xl flex-col gap-5" data-testid="remanejamentos-page">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGD", href: "/sgd" },
            { label: "Remanejamentos" },
          ]}
        />
        <Suspense fallback={<Carregando />}>
          <FilaRemanejamentosView />
        </Suspense>
      </div>
    </>
  );
}
