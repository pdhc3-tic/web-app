"use client";

import { Select } from "@/app/components/ui/Select/Select";
import { formatCurrencyBRL } from "@/app/lib/format";
import { usePoolsDeOrigem } from "@/app/lib/hooks/usePoolsDeOrigem";
import type { PedidoRecursoExtra } from "@/app/lib/remanejamentos";

/**
 * Pool de origem do remanejamento (#321): aparece quando o backend recusa
 * a aprovação porque o pool territorial não cobre a demanda. A UGP escolhe de
 * onde sai a diferença; o backend remaneja na própria decisão e valida o
 * nível e o saldo.
 *
 * As opções vêm de `usePoolsDeOrigem`: os estaduais e o nacional da rubrica.
 */
export function OrigemAlocacao({
  pedido,
  value,
  onChange,
}: {
  pedido: PedidoRecursoExtra;
  value: string;
  onChange: (value: string) => void;
}) {
  const { pools, carregando, falhou } = usePoolsDeOrigem([pedido.rubrica]);

  return (
    <div data-testid="origem-alocacao">
      <Select
        label="Pool de origem do remanejamento"
        required
        disabled={carregando || pools.length === 0}
        placeholder={carregando ? "Carregando origens…" : "Selecione a origem"}
        options={pools.map((p) => ({
          value: String(p.id),
          label: `${p.estado?.nome ?? "Nacional"} — saldo ${formatCurrencyBRL(p.saldo_pool)}`,
        }))}
        value={value}
        onChange={onChange}
        helperText={
          falhou
            ? "Não foi possível carregar as origens. Tente de novo."
            : !carregando && pools.length === 0
              ? "Nenhum pool estadual ou nacional desta rubrica."
              : "O pool territorial não cobre a demanda: a diferença sai deste pool."
        }
      />
    </div>
  );
}
