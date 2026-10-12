"use client";

import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { FileText, Plus } from "lucide-react";
import { CrudTab } from "@/app/components/sgp/CrudTab/CrudTab";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { ApiError } from "@/app/lib/api";
import { canCreateDemanda } from "@/app/lib/auth/roles";
import { absoluteDateTime } from "@/app/lib/datetime";
import {
  badgeStatusDaDemanda,
  listDemandasDaAtividade,
  STATUS_ATIVIDADE_BLOQUEIAM_DEMANDA,
  type Demanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import type { AtividadeDetail } from "@/app/lib/atividades";

function DemandasSkeleton() {
  return (
    <ul className="flex list-none flex-col gap-2" aria-busy="true">
      {[0, 1].map((i) => (
        <li
          key={i}
          className="h-[72px] animate-pulse rounded-lg border border-border bg-surface-muted"
        />
      ))}
    </ul>
  );
}

/**
 * Aba "Demandas" da ficha da Atividade (#294, SGD-RF01).
 *
 * Lista as demandas da atividade, cada uma com o próprio status, e leva ao
 * formulário do SGD com a atividade já escolhida. A criação mora no SGD — a
 * aba é só a porta de entrada contextualizada.
 */
export function DemandasTab({ atividade }: { atividade: AtividadeDetail }) {
  const { data: session } = useSession();
  const podeCriar = canCreateDemanda(session?.user);
  const bloqueada = STATUS_ATIVIDADE_BLOQUEIAM_DEMANDA.includes(atividade.status);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: qk.demandasDaAtividade(atividade.id),
    queryFn: ({ signal }) => listDemandasDaAtividade(atividade.id, signal),
  });

  const demandas: Demanda[] = data ?? [];
  const mensagemErro =
    error instanceof ApiError
      ? error.message
      : error
        ? "Não foi possível carregar as demandas."
        : null;

  const novaHref = `/sgd/demandas/nova?atividade=${atividade.id}`;

  return (
    <div className="flex flex-col gap-4" data-testid="atividade-demandas">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-text-muted">
          Pedidos de recurso do SGD vinculados a esta atividade.
        </p>
        {podeCriar &&
          (bloqueada ? (
            // O link não tem estado desabilitado: com a atividade bloqueada o
            // controle vira botão inerte, explicando o porquê no title.
            <Button
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              disabled
              title="Atividades canceladas ou não realizadas não aceitam novas demandas."
              data-testid="demanda-nova-btn"
            >
              Nova demanda
            </Button>
          ) : (
            <Button
              as="a"
              href={novaHref}
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              data-testid="demanda-nova-btn"
            >
              Nova demanda
            </Button>
          ))}
      </div>

      <CrudTab
        loading={isPending}
        error={mensagemErro}
        onRetry={() => void refetch()}
        skeleton={<DemandasSkeleton />}
      >
        {demandas.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<FileText className="h-7 w-7" />}
              title="Nenhuma demanda para esta atividade"
              description={
                podeCriar && !bloqueada
                  ? "Use “Nova demanda” para pedir recursos para esta atividade."
                  : "Quando o técnico abrir um pedido de recurso, ele aparece aqui."
              }
            />
          </div>
        ) : (
          <ul className="flex list-none flex-col gap-2" data-testid="demandas-lista">
            {demandas.map((d) => (
              <li
                key={d.id}
                data-testid={`demanda-${d.id}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text">{d.titulo}</p>
                  <p className="mt-0.5 text-xs text-text-muted">
                    Aberta em {absoluteDateTime(d.criado_em)}
                    {d.despesa_posterior && " · despesa posterior à execução"}
                  </p>
                </div>
                <span className="text-sm tabular-nums text-text-muted">
                  {formatCurrencyBRL(d.valor_estimado_total)}
                </span>
                <Badge status={badgeStatusDaDemanda(d.status)} label={d.status_display} />
              </li>
            ))}
          </ul>
        )}
      </CrudTab>

      {podeCriar && bloqueada && (
        <p className="text-xs text-text-muted">
          Esta atividade está em um status que não aceita novas demandas.
        </p>
      )}
    </div>
  );
}
