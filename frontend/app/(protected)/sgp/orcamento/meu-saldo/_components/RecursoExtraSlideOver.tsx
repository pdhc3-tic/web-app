"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Plus } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { badgeStatusDaDemanda, listDemandas } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import type { SaldoDaRubrica } from "@/app/lib/meuSaldo";
import { qk } from "@/app/lib/queryKeys";

/**
 * Atalho "Solicitar recurso extra" a partir de uma rubrica do "Meu saldo"
 * (#401 → #321).
 *
 * O backend só aceita o pedido a partir de uma demanda em Rascunho ou Devolvida
 * que tenha solicitação na rubrica (`recurso_extra.criar`): o valor que falta
 * sai dela. Por isso o atalho lista essas demandas e leva à montagem, onde a
 * submissão barrada oferece o pedido. Sem nenhuma, explica e oferece criar.
 */
export function RecursoExtraSlideOver({
  saldo,
  onClose,
}: {
  saldo: SaldoDaRubrica | null;
  onClose: () => void;
}) {
  return (
    <SlideOver
      open={!!saldo}
      onClose={onClose}
      title={saldo ? `Recurso extra — ${saldo.rubrica_nome}` : "Recurso extra"}
    >
      {saldo && <DemandasEditaveis saldo={saldo} />}
    </SlideOver>
  );
}

function DemandasEditaveis({ saldo }: { saldo: SaldoDaRubrica }) {
  const { data: session } = useSession();
  const eu = session?.user?.id ? String(session.user.id) : undefined;

  const demandas = useQuery({
    queryKey: qk.meuSaldo.demandasParaRecurso(saldo.rubrica),
    queryFn: ({ signal }) =>
      listDemandas(
        { status: ["rascunho", "devolvida"], filtros: { solicitante: eu, rubrica: saldo.rubrica } },
        signal,
      ),
    enabled: !!eu,
    staleTime: 0,
  });

  return (
    <div className="flex flex-col gap-4 px-4 py-4" data-testid="recurso-extra-atalho-painel">
      <p className="text-sm text-text-muted">
        O recurso extra é pedido a partir de uma demanda que tenha solicitação em{" "}
        <strong className="text-text">{saldo.rubrica_nome}</strong> e ainda não foi submetida. Abra a
        demanda e submeta: se o limite barrar, a própria tela oferece o pedido, com o valor que falta.
      </p>
      <p className="text-sm text-text-muted">
        Disponível hoje na rubrica:{" "}
        <strong className="tabular-nums text-text">{formatCurrencyBRL(saldo.disponivel)}</strong>
      </p>

      {demandas.isPending ? (
        <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
          <Spinner className="h-4 w-4 animate-spin" /> Buscando as suas demandas…
        </p>
      ) : demandas.error ? (
        <TabErroSection
          message={demandas.error instanceof ApiError ? demandas.error.message : "Não foi possível buscar as demandas."}
          onRetry={() => void demandas.refetch()}
        />
      ) : demandas.data.demandas.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-md border border-dashed border-border p-4">
          <p className="text-sm text-text" data-testid="recurso-extra-sem-demanda">
            Você não tem demanda em Rascunho ou Devolvida com solicitação nesta rubrica.
          </p>
          <Button
            as="a"
            href="/sgd/demandas/nova"
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            data-testid="recurso-extra-nova-demanda"
          >
            Nova demanda
          </Button>
        </div>
      ) : (
        <ul className="flex flex-col gap-2" data-testid="recurso-extra-demandas">
          {demandas.data.demandas.map((d) => (
            <li key={d.id}>
              <Link
                href={`/sgd/demandas/${d.id}/editar`}
                className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2.5 hover:bg-surface-muted/60 focus-visible:outline-2 focus-visible:outline-primary"
                data-testid={`recurso-extra-demanda-${d.id}`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-text">{d.titulo}</span>
                  <span className="text-xs tabular-nums text-text-muted">
                    Estimado {formatCurrencyBRL(d.valor_estimado_total)}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <Badge status={badgeStatusDaDemanda(d.status)} label={d.status_display} />
                  <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
