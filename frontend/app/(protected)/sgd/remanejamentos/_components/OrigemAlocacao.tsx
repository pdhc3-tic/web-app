"use client";

import { useQuery } from "@tanstack/react-query";
import { Select } from "@/app/components/ui/Select/Select";
import { getAtividade } from "@/app/lib/atividades";
import { formatCurrencyBRL } from "@/app/lib/format";
import { fetchOrcamentoDaMeta } from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";
import type { PedidoRecursoExtra } from "@/app/lib/remanejamentos";

/**
 * Alocação de origem do remanejamento (#321): aparece quando o backend recusa
 * a aprovação porque o pool territorial não cobre a demanda. A UGP escolhe de
 * onde sai a diferença; o backend remaneja na própria decisão e valida o
 * nível e o saldo.
 *
 * As opções são as alocações ESTADUAIS da rubrica na Meta da atividade
 * (`GET /sgp/metas/{id}/orcamento/`). As nacionais não vêm nesse detalhamento
 * — o backend as aceita, mas não há de onde listá-las.
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
  const atividade = useQuery({
    queryKey: qk.atividade(pedido.activity ?? ""),
    queryFn: ({ signal }) => getAtividade(pedido.activity!, signal),
    enabled: pedido.activity !== null,
  });
  const metaId = atividade.data?.acao.meta?.id;

  const orcamento = useQuery({
    queryKey: qk.orcamentoDaMeta(metaId ?? 0),
    queryFn: ({ signal }) => fetchOrcamentoDaMeta(metaId!, signal),
    enabled: metaId !== undefined,
  });

  const alocacoes =
    orcamento.data
      ?.find((r) => r.rubrica.slug === pedido.rubrica)
      ?.detalhamento.filter((a) => a.nivel === "estadual") ?? [];

  const carregando = atividade.isPending || (metaId !== undefined && orcamento.isPending);

  return (
    <div data-testid="origem-alocacao">
      <Select
        label="Alocação de origem do remanejamento"
        required
        disabled={carregando || alocacoes.length === 0}
        placeholder={carregando ? "Carregando alocações…" : "Selecione a alocação estadual"}
        options={alocacoes.map((a) => ({
          value: String(a.id),
          label: `${a.estado?.nome ?? "Estadual"} — saldo ${formatCurrencyBRL(a.saldo_disponivel)}`,
        }))}
        value={value}
        onChange={onChange}
        helperText={
          !carregando && alocacoes.length === 0
            ? "Nenhuma alocação estadual desta rubrica na Meta da atividade."
            : "O pool territorial não cobre a demanda: a diferença sai desta alocação."
        }
      />
    </div>
  );
}
