"use client";

import Link from "next/link";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import { badgeStatusDoPedido, type PedidoRecursoExtra } from "@/app/lib/remanejamentos";

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-middle";

/** Os pedidos de recurso extra da fila; cada um abre no próprio detalhe. */
export function PedidosTabela({ pedidos }: { pedidos: PedidoRecursoExtra[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm" data-testid="remanejamentos-tabela">
        <thead className="border-b border-border bg-surface-muted/50">
          <tr>
            <th className={TH}>Pedido</th>
            <th className={TH}>Status</th>
            <th className={TH}>Solicitante</th>
            <th className={TH}>Rubrica</th>
            <th className={TH}>Pedido em</th>
            <th className={`${TH} text-right`}>Valor solicitado</th>
          </tr>
        </thead>
        <tbody>
          {pedidos.map((p) => (
            <tr
              key={p.id}
              data-testid={`pedido-linha-${p.id}`}
              className="border-b border-border transition-colors last:border-b-0 hover:bg-surface-muted/60"
            >
              <td className={TD}>
                <Link
                  href={`/sgd/remanejamentos/${p.id}`}
                  className="font-medium text-text hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  Pedido #{p.id}
                  {p.demanda_id && (
                    <span className="font-normal text-text-muted"> · demanda #{p.demanda_id}</span>
                  )}
                </Link>
              </td>
              <td className={TD}>
                <Badge status={badgeStatusDoPedido(p.status)} label={p.status_display} />
              </td>
              <td className={`${TD} text-text-muted`}>{p.solicitante_nome}</td>
              <td className={`${TD} text-text-muted`}>{p.rubrica_nome}</td>
              <td className={`${TD} tabular-nums text-text-muted`}>{formatDate(p.criado_em)}</td>
              <td className={`${TD} text-right tabular-nums text-text`}>
                {formatCurrencyBRL(p.valor_solicitado)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
