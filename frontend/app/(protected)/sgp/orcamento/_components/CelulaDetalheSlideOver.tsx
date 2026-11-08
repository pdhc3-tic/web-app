"use client";

import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  fetchTransacoesDoPool,
  labelSemaforoOrcamento,
  limiaresDaLinha,
  nivelOrcamentoLabel,
  nomeDoPool,
  TIPO_TRANSACAO_LABEL,
  type TransacaoPoolApi,
} from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";
import { formatPercentual } from "@/app/lib/semaforo";
import type { CelulaOrcamento } from "./tipos";

function Movimentacao({ t }: { t: TransacaoPoolApi }) {
  return (
    <li className="flex flex-col gap-0.5 rounded-md border border-border px-3 py-2" data-testid={`orcamento-transacao-${t.id}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-text">{TIPO_TRANSACAO_LABEL[t.tipo] ?? t.tipo}</span>
        <span className="text-sm tabular-nums text-text">{formatCurrencyBRL(t.valor)}</span>
      </div>
      <p className="text-xs text-text-muted">
        {absoluteDateTime(t.criado_em)}
        {t.demanda_id && ` · demanda #${t.demanda_id}`}
        {t.saldo_posterior !== null && ` · saldo depois ${formatCurrencyBRL(t.saldo_posterior)}`}
      </p>
      {t.justificativa && <p className="whitespace-pre-wrap text-xs text-text">{t.justificativa}</p>}
    </li>
  );
}

/**
 * Detalhe de um pool da matriz (#398): os valores, o semáforo e o histórico de
 * movimentações do ledger (`GET /sgp/orcamento/pools/{id}/transacoes/`), que
 * substitui o detalhamento por Meta do orçamento antigo.
 */
export function CelulaDetalheSlideOver({
  celula,
  onClose,
}: {
  celula: CelulaOrcamento | null;
  onClose: () => void;
}) {
  const pool = celula?.linha;
  const transacoes = useQuery({
    queryKey: qk.orcamentoPool.transacoes(pool?.id ?? 0),
    queryFn: ({ signal }) => fetchTransacoesDoPool(pool!.id, signal),
    enabled: !!pool,
  });

  return (
    <SlideOver
      open={!!celula}
      onClose={onClose}
      title={pool ? `${pool.rubrica.nome} — ${nomeDoPool(pool)}` : "Pool"}
      width="wide"
    >
      {celula && pool && (
        <div className="flex flex-col gap-5 px-4 py-4" data-testid="orcamento-detalhe">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-surface-muted px-2 py-0.5 text-2xs font-medium uppercase tracking-[0.06em] text-text-muted">
              {nivelOrcamentoLabel(pool.nivel)}
            </span>
            <SemaforoBadge
              nivel={celula.nivelSemaforo}
              label={labelSemaforoOrcamento(celula.nivelSemaforo, limiaresDaLinha(pool))}
            />
            <span className="text-xs tabular-nums text-text-muted">{formatPercentual(celula.percentual)} comprometido</span>
          </div>

          <DefinitionList
            items={[
              { label: "Aprovado", value: formatCurrencyBRL(pool.valor_aprovado) },
              { label: "Distribuído aos níveis abaixo", value: formatCurrencyBRL(pool.valor_distribuido) },
              { label: "Comprometido", value: formatCurrencyBRL(pool.valor_comprometido) },
              { label: "Executado", value: formatCurrencyBRL(pool.valor_executado) },
              { label: "Disponível", value: formatCurrencyBRL(pool.saldo_disponivel) },
            ]}
          />

          <section className="flex flex-col gap-2" aria-labelledby="orcamento-historico-titulo">
            <h3 id="orcamento-historico-titulo" className="text-sm font-semibold text-text">
              Movimentações
            </h3>
            {transacoes.isPending ? (
              <p className="flex items-center gap-2 text-sm text-text-muted">
                <Spinner className="h-4 w-4 animate-spin" /> Carregando movimentações…
              </p>
            ) : transacoes.isError ? (
              <p role="alert" className="text-sm text-error-text">
                {transacoes.error instanceof ApiError
                  ? transacoes.error.message
                  : "Não foi possível carregar as movimentações."}
              </p>
            ) : transacoes.data.length === 0 ? (
              <EmptyState
                icon={<History className="h-6 w-6" />}
                title="Sem movimentações"
                description="Nenhuma reserva, execução ou remanejamento passou por este pool ainda."
              />
            ) : (
              <ul className="flex flex-col gap-2" data-testid="orcamento-transacoes">
                {transacoes.data.map((t) => (
                  <Movimentacao key={t.id} t={t} />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </SlideOver>
  );
}
