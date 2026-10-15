"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { canCreateDemanda } from "@/app/lib/auth/roles";
import { NovaDemandaForm } from "../_components/NovaDemandaForm";

function Carregando() {
  return (
    <div
      role="status"
      className="flex min-h-[40vh] items-center justify-center gap-2 text-sm text-text-muted"
    >
      <Spinner className="h-5 w-5 animate-spin" />
      Carregando…
    </div>
  );
}

function NovaDemandaView() {
  const searchParams = useSearchParams();
  const { data: session, status } = useSession();

  // `?atividade={id}` chega da aba Demandas da ficha da atividade.
  const bruto = searchParams.get("atividade") ?? "";
  const atividadeId = /^\d+$/.test(bruto) ? Number(bruto) : null;

  if (status === "loading") return <Carregando />;
  if (!canCreateDemanda(session?.user)) return <RestrictedAccess />;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGD", href: "/sgd" },
          ...(atividadeId !== null
            ? [
                {
                  label: "Atividade",
                  href: `/sgp/atividades/${atividadeId}?tab=demandas`,
                },
              ]
            : []),
          { label: "Nova demanda" },
        ]}
      />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">
          Nova demanda
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          A demanda é criada como rascunho e pode ser completada antes de ser
          submetida para aprovação.
        </p>
      </div>
      <NovaDemandaForm atividadeIdInicial={atividadeId} />
    </div>
  );
}

export default function NovaDemandaPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>
      <Suspense fallback={<Carregando />}>
        <NovaDemandaView />
      </Suspense>
    </>
  );
}
