"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import Spinner from "@/app/components/icons/Spinner";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { canVerMeuSaldo } from "@/app/lib/auth/roles";
import { fetchMeuSaldo, type SaldoDaRubrica } from "@/app/lib/meuSaldo";
import { qk } from "@/app/lib/queryKeys";
import { CardSaldo } from "./_components/CardSaldo";
import { ExtratoSlideOver } from "./_components/ExtratoSlideOver";
import { RecursoExtraSlideOver } from "./_components/RecursoExtraSlideOver";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

/**
 * "Meu saldo" (#401, SGP §6.5): quanto a pessoa ainda pode solicitar em cada
 * rubrica, pelo limite individual do período, com o extrato de cada uma e o
 * atalho do recurso extra quando o limite aperta.
 *
 * É a leitura do LIMITE da pessoa. O saldo do POOL do território — a segunda
 * trava — continua no card do Painel de Orçamento; aqui aparece só como nota.
 */
export default function MeuSaldoPage() {
  const { data: session, status } = useSession();
  const pode = canVerMeuSaldo(session?.user);
  const [extrato, setExtrato] = useState<SaldoDaRubrica | null>(null);
  const [recurso, setRecurso] = useState<SaldoDaRubrica | null>(null);

  const saldos = useQuery({
    queryKey: qk.meuSaldo.cards,
    queryFn: ({ signal }) => fetchMeuSaldo(signal),
    // O saldo muda por fluxos de outras telas (submissão, autorização,
    // cancelamento): sempre busca de novo ao abrir, sem confiar no cache.
    staleTime: 0,
    enabled: pode,
  });

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Meu saldo</h1>
    </PageHeader>
  );

  if (status === "loading") return <CenteredSpinner />;

  if (!pode) {
    return (
      <>
        {header}
        <RestrictedAccess
          title="Sem limite de gasto"
          description="O Meu saldo mostra os limites de quem solicita recursos: ADT/ACR e Articulador Estadual. Os valores do projeto estão no Painel de Orçamento."
        />
      </>
    );
  }

  return (
    <div data-testid="meu-saldo-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Painel de Orçamento", href: "/sgp/orcamento" },
            { label: "Meu saldo" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          Quanto você ainda pode solicitar em cada rubrica neste período. A demanda submetida reserva o
          valor; a autorização e o pagamento o transformam em executado; a recusa e o cancelamento o
          devolvem.
        </p>

        {saldos.isPending ? (
          <CenteredSpinner />
        ) : saldos.error ? (
          <TabErroSection
            message={saldos.error instanceof ApiError ? saldos.error.message : "Não foi possível carregar o seu saldo."}
            onRetry={() => void saldos.refetch()}
          />
        ) : saldos.data.length === 0 ? (
          <EmptyState
            title="Nenhum limite definido para você"
            description="Sem limite em nenhuma rubrica, nenhuma demanda sua pode ser submetida. Fale com a UGP."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="meu-saldo-cards">
            {saldos.data.map((s) => (
              <CardSaldo
                key={s.rubrica}
                saldo={s}
                onExtrato={() => setExtrato(s)}
                onRecursoExtra={() => setRecurso(s)}
              />
            ))}
          </div>
        )}
      </div>

      <ExtratoSlideOver saldo={extrato} onClose={() => setExtrato(null)} />
      <RecursoExtraSlideOver saldo={recurso} onClose={() => setRecurso(null)} />
    </div>
  );
}
