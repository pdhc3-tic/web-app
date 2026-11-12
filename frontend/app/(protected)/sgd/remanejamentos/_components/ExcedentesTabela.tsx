"use client";

import Link from "next/link";
import { Scale } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import type { PoolDoRemanejamento, TransferenciaRemanejamento } from "@/app/lib/remanejamentos";

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-middle";

const nomeDoPool = (a: PoolDoRemanejamento) => a.territorio ?? a.estado ?? "Nacional";

/** Os excedentes autorizados nas demandas (#363): remanejamentos pontuais, sem pedido de recurso extra. */
export function ExcedentesTabela({
  excedentes,
  total,
}: {
  excedentes: TransferenciaRemanejamento[];
  total: number;
}) {
  if (excedentes.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface">
        <EmptyState
          icon={<Scale className="h-7 w-7" />}
          title="Nenhum excedente autorizado"
          description="Os excedentes autorizados pela UGP nas demandas aparecem aqui."
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full text-sm" data-testid="excedentes-tabela">
          <thead className="border-b border-border bg-surface-muted/50">
            <tr>
              <th className={TH}>Demanda</th>
              <th className={TH}>Tipo</th>
              <th className={TH}>Rubrica</th>
              <th className={TH}>Origem → destino</th>
              <th className={TH}>Autorizado por</th>
              <th className={TH}>Em</th>
              <th className={`${TH} text-right`}>Valor</th>
            </tr>
          </thead>
          <tbody>
            {excedentes.map((e) => (
              <tr
                key={e.id}
                data-testid={`excedente-linha-${e.id}`}
                className="border-b border-border transition-colors last:border-b-0 hover:bg-surface-muted/60"
              >
                <td className={TD}>
                  <Link
                    href={`/sgd/demandas?demanda=${e.demanda_id}`}
                    className="font-medium text-text hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    Demanda #{e.demanda_id}
                  </Link>
                </td>
                <td className={TD}>
                  <Badge status="agendado" label="Pontual" />
                </td>
                <td className={`${TD} text-text-muted`}>{e.rubrica}</td>
                <td className={`${TD} text-text-muted`}>
                  {nomeDoPool(e.origem)} → {nomeDoPool(e.destino)}
                </td>
                <td className={`${TD} text-text-muted`}>{e.aprovado_por_nome ?? "—"}</td>
                <td className={`${TD} tabular-nums text-text-muted`}>{formatDate(e.criado_em)}</td>
                <td className={`${TD} text-right tabular-nums text-text`}>{formatCurrencyBRL(e.valor)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > excedentes.length && (
        <p role="status" className="text-xs text-text-muted" data-testid="excedentes-lista-parcial">
          Mostrando {excedentes.length} de {total} excedentes.
        </p>
      )}
    </div>
  );
}
