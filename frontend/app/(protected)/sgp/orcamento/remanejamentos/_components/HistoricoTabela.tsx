"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { formatDate, formatTime } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import { RUBRICAS } from "@/app/lib/orcamento";
import {
  TIPO_DA_TRANSFERENCIA,
  nomeDoPoolDoRemanejamento as nomeDoPool,
  origemDaTransferencia,
  type TransferenciaRemanejamento,
} from "@/app/lib/remanejamentos";

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-top";

const nomeDaRubrica = (slug: string) => RUBRICAS.find((r) => r.slug === slug)?.nome ?? slug;

function Saldos({ antes, depois, testId }: { antes: string; depois: string; testId: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap tabular-nums" data-testid={testId}>
      <span className="text-text-muted">{formatCurrencyBRL(antes)}</span>
      <ArrowRight className="h-3.5 w-3.5 text-text-muted" aria-label="para" />
      <span className="font-medium text-text">{formatCurrencyBRL(depois)}</span>
    </span>
  );
}

/**
 * Remanejamentos efetivados (#466): o que saiu de onde para onde, os saldos
 * dos dois pools antes e depois, quem aprovou e por quê.
 */
export function HistoricoTabela({ transferencias }: { transferencias: TransferenciaRemanejamento[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm" data-testid="historico-remanejamentos-tabela">
        <thead className="border-b border-border bg-surface-muted/50">
          <tr>
            <th className={TH}>Em</th>
            <th className={TH}>Remanejamento</th>
            <th className={TH}>Saldo da origem</th>
            <th className={TH}>Saldo do destino</th>
            <th className={TH}>Aprovado por</th>
            <th className={`${TH} text-right`}>Valor</th>
          </tr>
        </thead>
        <tbody>
          {transferencias.map((t) => {
            const origem = origemDaTransferencia(t);
            const id = `remanejamento-${t.id}`;
            return (
              <tr
                key={t.id}
                data-testid={id}
                className="border-b border-border transition-colors last:border-b-0 hover:bg-surface-muted/60"
              >
                <td className={`${TD} whitespace-nowrap tabular-nums text-text-muted`} data-testid={`${id}-em`}>
                  {formatDate(t.criado_em)}
                  <span className="block text-xs">{formatTime(t.criado_em)}</span>
                </td>
                <td className={`${TD} min-w-[18rem]`}>
                  <p className="font-medium text-text" data-testid={`${id}-pools`}>
                    {nomeDoPool(t.origem)} → {nomeDoPool(t.destino)}
                  </p>
                  <p className="mt-0.5 text-xs text-text-muted">
                    <span data-testid={`${id}-rubrica`}>{nomeDaRubrica(t.rubrica)}</span>
                    {" · "}
                    {TIPO_DA_TRANSFERENCIA[t.tipo] ?? t.tipo}
                    {" · "}
                    {origem.href ? (
                      <Link
                        href={origem.href}
                        className="text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                        data-testid={`${id}-origem`}
                      >
                        {origem.rotulo}
                      </Link>
                    ) : (
                      <span data-testid={`${id}-origem`}>{origem.rotulo}</span>
                    )}
                  </p>
                  {t.motivo && (
                    <p className="mt-1.5 max-w-prose text-xs text-text" data-testid={`${id}-motivo`}>
                      {t.motivo}
                    </p>
                  )}
                </td>
                <td className={TD}>
                  <Saldos antes={t.saldo_origem_antes} depois={t.saldo_origem_depois} testId={`${id}-saldo-origem`} />
                </td>
                <td className={TD}>
                  <Saldos antes={t.saldo_destino_antes} depois={t.saldo_destino_depois} testId={`${id}-saldo-destino`} />
                </td>
                <td className={`${TD} text-text-muted`} data-testid={`${id}-aprovado-por`}>
                  {t.aprovado_por_nome ?? "—"}
                </td>
                <td
                  className={`${TD} whitespace-nowrap text-right font-medium tabular-nums text-text`}
                  data-testid={`${id}-valor`}
                >
                  {formatCurrencyBRL(t.valor)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
