"use client";

import { Select } from "@/app/components/ui/Select/Select";
import { formatCurrencyBRL } from "@/app/lib/format";
import { useAlocacoesDeOrigem } from "@/app/lib/hooks/useAlocacoesDeOrigem";
import type { PedidoRecursoExtra } from "@/app/lib/remanejamentos";

/**
 * Alocação de origem do remanejamento (#321): aparece quando o backend recusa
 * a aprovação porque o pool territorial não cobre a demanda. A UGP escolhe de
 * onde sai a diferença; o backend remaneja na própria decisão e valida o
 * nível e o saldo.
 *
 * As opções vêm de `useAlocacoesDeOrigem`.
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
  const { alocacoes, carregando } = useAlocacoesDeOrigem(pedido.activity, [pedido.rubrica]);

  return (
    <div data-testid="origem-alocacao">
      <Select
        label="Alocação de origem do remanejamento"
        required
        disabled={carregando || alocacoes.length === 0}
        placeholder={carregando ? "Carregando alocações…" : "Selecione a alocação"}
        options={alocacoes.map((a) => ({
          value: String(a.id),
          label: `${a.estado?.nome ?? "Nacional"} — saldo ${formatCurrencyBRL(a.saldo_disponivel)}`,
        }))}
        value={value}
        onChange={onChange}
        helperText={
          !carregando && alocacoes.length === 0
            ? "Nenhuma alocação estadual ou nacional desta rubrica na Meta da atividade."
            : "O pool territorial não cobre a demanda: a diferença sai desta alocação."
        }
      />
    </div>
  );
}
