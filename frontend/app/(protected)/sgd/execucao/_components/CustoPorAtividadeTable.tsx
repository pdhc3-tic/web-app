"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  queryDeFiltros,
  type EntregaCusto,
  type ExecucaoFiltros,
} from "@/app/lib/execucaoSgd";

/**
 * Link do drill-down para a lista de demandas, levando os filtros ativos do
 * painel — a lista mostra as mesmas demandas que compõem o custo exibido.
 */
function hrefDemandas(filtros: ExecucaoFiltros, recorte: ExecucaoFiltros): string {
  const qs = queryDeFiltros({ ...filtros, ...recorte });
  return `/sgd/demandas?${qs}`;
}

/**
 * Esqueleto do relatório, com cards do mesmo tamanho dos reais. Evita o salto
 * de layout da #323 enquanto o backend responde.
 */
export function CustoPorAtividadeTableSkeleton({ cards = 3 }: { cards?: number }) {
  return (
    <div
      className="space-y-4"
      aria-hidden
      data-testid="custo-por-atividade-skeleton"
    >
      {Array.from({ length: cards }).map((_, i) => (
        <div
          key={i}
          className="overflow-hidden rounded-lg border border-border bg-surface shadow-xs"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-muted/60 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 animate-pulse rounded bg-surface-muted" />
              <div className="flex flex-col gap-1.5">
                <div className="h-3 w-28 animate-pulse rounded bg-surface-muted" />
                <div className="h-4 w-56 animate-pulse rounded bg-surface-muted" />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              {Array.from({ length: 4 }).map((__, j) => (
                <div key={j} className="h-4 w-24 animate-pulse rounded bg-surface-muted" />
              ))}
            </div>
          </div>
          <div className="divide-y divide-border">
            {Array.from({ length: 3 }).map((__, j) => (
              <div key={j} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="h-4 w-64 animate-pulse rounded bg-surface-muted" />
                <div className="flex items-center gap-6">
                  <div className="h-4 w-20 animate-pulse rounded bg-surface-muted" />
                  <div className="h-4 w-20 animate-pulse rounded bg-surface-muted" />
                  <div className="h-4 w-20 animate-pulse rounded bg-surface-muted" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CustoPorAtividadeTable({
  entregas,
  filtros,
}: {
  entregas: EntregaCusto[];
  filtros: ExecucaoFiltros;
}) {
  // Entregas começam abertas; guarda só as que o usuário recolheu.
  const [recolhidas, setRecolhidas] = useState<Record<number, boolean>>({});

  const alternar = (acaoId: number) =>
    setRecolhidas((prev) => ({ ...prev, [acaoId]: !prev[acaoId] }));

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
        const aberta = !recolhidas[entrega.acao_id];
        const idCorpo = `entrega-${entrega.acao_id}-atividades`;

        return (
          <div
            key={entrega.acao_id}
            className="overflow-hidden rounded-lg border border-border bg-surface shadow-xs"
            data-testid={`entrega-${entrega.acao_id}`}
          >
            {/* Cabeçalho da entrega (Ação do Plano de Trabalho) */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-muted/60 px-4 py-3">
              <button
                type="button"
                onClick={() => alternar(entrega.acao_id)}
                aria-expanded={aberta}
                aria-controls={idCorpo}
                className="flex items-center gap-2 rounded text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                {aberta ? (
                  <ChevronDown className="h-4 w-4 shrink-0 text-text-muted" aria-hidden />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" aria-hidden />
                )}
                <span>
                  <span className="block text-xs font-semibold uppercase tracking-wider text-text-muted">
                    Ação {entrega.acao_numero}
                  </span>
                  <span className="block text-sm font-semibold text-text">
                    {entrega.acao_descricao}
                  </span>
                </span>
              </button>

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
                  <span className="font-semibold text-primary">
                    {formatCurrencyBRL(entrega.pago)}
                  </span>
                </span>
                <Link
                  href={hrefDemandas(filtros, { acao: String(entrega.acao_id), atividade: undefined })}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium text-primary hover:bg-primary/10 hover:underline"
                  data-testid={`link-demandas-entrega-${entrega.acao_id}`}
                >
                  <span>Ver demandas da entrega</span>
                  <ExternalLink className="h-3 w-3" aria-hidden />
                </Link>
              </div>
            </div>

            {/* Atividades vinculadas à entrega */}
            {aberta && (
              <div className="overflow-x-auto" id={idCorpo}>
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
                            href={hrefDemandas(filtros, { atividade: String(atv.atividade_id) })}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 hover:underline"
                            data-testid={`link-demandas-${atv.atividade_id}`}
                          >
                            <span>Ver demandas</span>
                            <ExternalLink className="h-3 w-3" aria-hidden />
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
