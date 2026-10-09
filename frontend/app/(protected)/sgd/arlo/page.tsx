"use client";

import { useSession } from "next-auth/react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { canOperarArlo } from "@/app/lib/auth/roles";
import { ExportarArlo } from "./_components/ExportarArlo";
import { HistoricoArlo } from "./_components/HistoricoArlo";
import { ImportarRetorno } from "./_components/ImportarRetorno";

/**
 * Integração Arlo (#298 · SGD-FE-5) — tela operacional da FGD para o fluxo
 * bidirecional: exportar as demandas autorizadas, importar o retorno de
 * pagamento e consultar o histórico das duas operações.
 *
 * Só FGD e Super Admin operam (`IsFGD | IsSuperAdmin` no `ArloViewSet`). O
 * gate aqui só evita mostrar uma tela que o backend recusaria.
 */
export default function ArloPage() {
  const { data: session, status } = useSession();

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">Integração Arlo</span>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-8" data-testid="arlo-page">
        <div>
          <Breadcrumb
            items={[
              { label: "Início", href: "/dashboard" },
              { label: "SGD", href: "/sgd" },
              { label: "Integração Arlo" },
            ]}
          />
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-text">Integração Arlo</h1>
          <p className="mt-1 text-sm text-text-muted">
            Envio das demandas autorizadas para pagamento e retorno dos pagamentos feitos pelo Arlo.
          </p>
        </div>

        {status === "loading" ? (
          <div className="flex items-center gap-2 py-10 text-sm text-text-muted">
            <Spinner className="h-4 w-4" /> Carregando…
          </div>
        ) : !canOperarArlo(session?.user) ? (
          <RestrictedAccess description="A integração com o Arlo é operada pela FGD. Disponível para FGD e Super Admin." />
        ) : (
          <>
            <ExportarArlo />
            <ImportarRetorno />
            <HistoricoArlo />
          </>
        )}
      </div>
    </>
  );
}
