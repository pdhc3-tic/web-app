"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { FileText, Plus } from "lucide-react";
import { AvisoListaParcial } from "@/app/(protected)/sgd/demandas/_components/AvisoListaParcial";
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
  type StatusDemanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { podeMontarDemanda } from "@/app/lib/solicitacoes";
import type { AtividadeDetail } from "@/app/lib/atividades";

/** Status em que a FGD já definiu o valor autorizado. */
const COM_VALOR_AUTORIZADO: StatusDemanda[] = ["autorizada", "em_atendimento", "concluida"];

/**
 * Rubricas e valores de uma demanda para a aba (#464, DRS 3.4). O autorizado
 * só existe depois da autorização, e o executado (o valor pago) só na
 * conclusão; antes disso, `null`, que a tela mostra como "—" em vez de R$ 0,00.
 */
export function resumoFinanceiro(d: Pick<Demanda, "status" | "solicitacoes" | "valor_estimado_total" | "valor_autorizado_total" | "valor_pago_total">) {
  return {
    rubricas: [...new Set(d.solicitacoes.map((s) => s.rubrica_nome))],
    estimado: d.valor_estimado_total,
    autorizado: COM_VALOR_AUTORIZADO.includes(d.status) ? d.valor_autorizado_total : null,
    executado: d.status === "concluida" ? d.valor_pago_total : null,
  };
}

function Valor({ rotulo, valor, testId }: { rotulo: string; valor: string | null; testId: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-2xs uppercase tracking-[0.08em] text-text-muted">{rotulo}</dt>
      <dd className="text-sm tabular-nums text-text" data-testid={testId}>
        {valor === null ? <span className="text-text-muted">—</span> : formatCurrencyBRL(valor)}
      </dd>
    </div>
  );
}

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

  const demandas: Demanda[] = data?.demandas ?? [];
  const mensagemErro =
    error instanceof ApiError
      ? error.message
      : error
        ? "Não foi possível carregar as demandas."
        : null;

  const novaHref = `/sgd/demandas/nova?atividade=${atividade.id}`;

  return (
    <div className="flex flex-col gap-4" data-testid="atividade-demandas">
      {/* Custo da atividade (#404): vem pronto do detalhe, sem somar no cliente. */}
      <dl
        className="grid grid-cols-2 gap-x-6 gap-y-1 rounded-lg border border-border bg-surface px-4 py-3 sm:max-w-md"
        data-testid="atividade-custos"
      >
        <div>
          <dt className="text-xs text-text-muted">Custo previsto</dt>
          <dd className="text-sm font-semibold tabular-nums text-text" data-testid="atividade-custo-previsto">
            {atividade.custo_previsto != null ? formatCurrencyBRL(atividade.custo_previsto) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-muted">Custo realizado</dt>
          <dd className="text-sm font-semibold tabular-nums text-text" data-testid="atividade-custo-realizado">
            {atividade.custo_realizado != null ? formatCurrencyBRL(atividade.custo_realizado) : "—"}
          </dd>
        </div>
      </dl>

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
            {demandas.map((d) => {
              const resumo = resumoFinanceiro(d);
              return (
                <li
                  key={d.id}
                  data-testid={`demanda-${d.id}`}
                  className="flex flex-col gap-3 rounded-lg border border-border bg-surface px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-text">{d.titulo}</p>
                      <p className="mt-0.5 text-xs text-text-muted">
                        Aberta em {absoluteDateTime(d.criado_em)}
                        {d.despesa_posterior && " · despesa posterior à execução"}
                      </p>
                    </div>
                    <Badge status={badgeStatusDaDemanda(d.status)} label={d.status_display} />
                    {podeMontarDemanda(d, session?.user?.id) && (
                      <Link
                        href={`/sgd/demandas/${d.id}/editar`}
                        className="text-sm font-medium text-primary hover:underline"
                        data-testid={`demanda-montar-${d.id}`}
                      >
                        Editar e submeter
                      </Link>
                    )}
                  </div>
                  <dl className="grid grid-cols-2 gap-x-6 gap-y-2 border-t border-border pt-3 sm:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))]">
                    <div className="col-span-2 flex min-w-0 flex-col sm:col-span-1">
                      <dt className="text-2xs uppercase tracking-[0.08em] text-text-muted">
                        {resumo.rubricas.length > 1 ? "Rubricas" : "Rubrica"}
                      </dt>
                      <dd className="text-sm text-text" data-testid={`demanda-${d.id}-rubricas`}>
                        {resumo.rubricas.length > 0 ? (
                          resumo.rubricas.join(", ")
                        ) : (
                          <span className="text-text-muted">Nenhuma solicitação</span>
                        )}
                      </dd>
                    </div>
                    <Valor rotulo="Estimado" valor={resumo.estimado} testId={`demanda-${d.id}-estimado`} />
                    <Valor rotulo="Autorizado" valor={resumo.autorizado} testId={`demanda-${d.id}-autorizado`} />
                    <Valor rotulo="Executado" valor={resumo.executado} testId={`demanda-${d.id}-executado`} />
                  </dl>
                </li>
              );
            })}
          </ul>
        )}
        <AvisoListaParcial lista={data} />
      </CrudTab>

      {podeCriar && bloqueada && (
        <p className="text-xs text-text-muted">
          Esta atividade está em um status que não aceita novas demandas.
        </p>
      )}
    </div>
  );
}
