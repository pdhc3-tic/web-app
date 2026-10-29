"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { getDemanda } from "@/app/lib/demandas";
import { qk } from "@/app/lib/queryKeys";
import { STATUS_DEMANDA_EDITAVEIS } from "@/app/lib/solicitacoes";
import { MontarDemanda } from "../../_components/montagem/MontarDemanda";

/**
 * Montar e submeter a demanda (#295). Só o solicitante, com a demanda em
 * Rascunho ou Devolvida — fora disso o backend recusa as alterações, e a tela
 * explica em vez de oferecer o que não vai funcionar.
 */
export default function MontarDemandaPage() {
  const { id } = useParams<{ id: string }>();
  const { data: session, status } = useSession();

  const { data: demanda, isPending, error, refetch } = useQuery({
    queryKey: qk.demandas.detalhe(id),
    queryFn: ({ signal }) => getDemanda(id, signal),
  });

  const ehSolicitante = !!demanda && String(demanda.solicitante) === String(session?.user?.id);

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>

      <div className="mx-auto flex max-w-4xl flex-col gap-5" data-testid="montar-demanda-page">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGD", href: "/sgd" },
            { label: "Demandas", href: "/sgd/demandas" },
            { label: demanda?.titulo ?? `Demanda #${id}` },
          ]}
        />

        {isPending || status === "loading" ? (
          <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
            <Spinner className="h-4 w-4 animate-spin" /> Carregando…
          </p>
        ) : error ? (
          <TabErroSection
            message={
              error instanceof ApiError && error.status === 404
                ? "Demanda não encontrada ou fora do seu escopo."
                : error instanceof ApiError
                  ? error.message
                  : "Não foi possível carregar a demanda."
            }
            onRetry={() => void refetch()}
          />
        ) : !demanda ? null : !ehSolicitante ? (
          <RestrictedAccess />
        ) : !STATUS_DEMANDA_EDITAVEIS.includes(demanda.status) ? (
          <p
            role="status"
            className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text"
            data-testid="montar-nao-editavel"
          >
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>
              A demanda está {demanda.status_display.toLowerCase()} e não pode mais ser alterada.{" "}
              <Link href={`/sgd/demandas?demanda=${demanda.id}`} className="font-medium underline">
                Acompanhar no painel de demandas
              </Link>
            </span>
          </p>
        ) : (
          <MontarDemanda demanda={demanda} />
        )}
      </div>
    </>
  );
}
