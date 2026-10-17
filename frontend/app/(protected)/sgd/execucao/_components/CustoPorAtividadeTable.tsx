"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { formatCurrencyBRL } from "@/app/lib/format";
import type { EntregaCusto } from "@/app/lib/execucaoSgd";

export function CustoPorAtividadeTable({
  entregas,
}: {
  entregas: EntregaCusto[];
}) {
  const [expandidas, setExpandidas] = useState<Record<number, boolean>>(() => {
    const init: Record<number, boolean> = {};
    for (const e of entregas) {
      init[e.acao_id] = true;
    }
    return init;
  });

  const toggleEntrega = (acaoId: number) => {
    setExpandidas((prev) => ({
      ...prev,
      [acaoId]: !prev[acaoId],
    }));
  };

  if (entregas.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center text-sm text-text-muted">
        Nenhum custo por atividade encontrado para os filtros selecionados.
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="relatorio-custo-por-atividade">
      {entregas.map((entrega) => {
        const aberta = expandidas[entrega.acao_id] ?? true;

        return (
          <div
            key={entrega.acao_id}
            className="overflow-hidden rounded-lg border border-border bg-surface shadow-xs"
            data-testid={`entrega-${entrega.acao_id}`}
          >
            {/* Header da Entrega (Ação do Plano de Trabalho) */}
            <div
              onClick={() => toggleEntrega(entrega.acao_id)}
              className="flex cursor-pointer flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-muted/60 px-4 py-3 transition-colors hover:bg-surface-muted"
            >
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  aria-label={aberta ? "Recolher entrega" : "Expandir entrega"}
                  className="text-text-muted hover:text-text"
                >
                  {aberta ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </button>
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                    Ação {entrega.acao_numero}
                  </span>
                  <h3 className="text-sm font-semibold text-text">
                    {entrega.acao_descricao}
                  </h3>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs font-medium tabular-nums text-text">
                <span>
                  <strong className="font-semibold text-text-muted">Demandas:</strong>{" "}
                  {entrega.demandas}
                </span>
                <span>
                  <strong className="font-semibold text-text-muted">Estimado:</strong>{" "}
                  {formatCurrencyBRL(entrega.estimado)}
                </span>
                <span>
                  <strong className="font-semibold text-text-muted">Autorizado:</strong>{" "}
                  {formatCurrencyBRL(entrega.autorizado)}
                </span>
                <span>
                  <strong className="font-semibold text-text-muted">Pago:</strong>{" "}
                  <span className="text-primary font-semibold">
                    {formatCurrencyBRL(entrega.pago)}
                  </span>
                </span>
              </div>
            </div>

            {/* Lista das atividades vinculadas à entrega */}
            {aberta && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-surface-muted/20 text-xs font-medium text-text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2.5">Atividade</th>
                      <th scope="col" className="px-4 py-2.5 text-center">Demandas</th>
                      <th scope="col" className="px-4 py-2.5 text-right">Estimado</th>
                      <th scope="col" className="px-4 py-2.5 text-right">Autorizado</th>
                      <th scope="col" className="px-4 py-2.5 text-right">Pago</th>
                      <th scope="col" className="px-4 py-2.5 text-center">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {entrega.atividades.map((atv) => (
                      <tr
                        key={atv.atividade_id}
                        className="transition-colors hover:bg-surface-warm/30"
                        data-testid={`atividade-linha-${atv.atividade_id}`}
                      >
                        <td className="px-4 py-3 font-medium text-text">
                          {atv.atividade_titulo}
                        </td>
                        <td className="px-4 py-3 text-center tabular-nums text-text">
                          {atv.demandas}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-text">
                          {formatCurrencyBRL(atv.estimado)}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-text">
                          {formatCurrencyBRL(atv.autorizado)}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums font-medium text-text">
                          {formatCurrencyBRL(atv.pago)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <Link
                            href={`/sgd/demandas?atividade=${atv.atividade_id}`}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 hover:underline"
                            data-testid={`link-demandas-${atv.atividade_id}`}
                          >
                            <span>Ver demandas</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
