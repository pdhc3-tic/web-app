"use client";

import { AlertTriangle, ChevronRight } from "lucide-react";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { formatCurrencyBRL } from "@/app/lib/format";
import { LIMIAR_ALERTA_PCT, labelSemaforoOrcamento } from "@/app/lib/orcamento";
import { formatPercentual } from "@/app/lib/semaforo";
import type { CelulaOrcamento } from "./tipos";

type Props = {
  celulas: CelulaOrcamento[];
  onSelect: (celula: CelulaOrcamento) => void;
};

/**
 * "Alocações que exigem atenção" — o banner de ≥ 80% comprometido.
 *
 * Fica no topo e reúne TODAS as alocações em vermelho, atravessando as Metas:
 * o ponto do requisito é que o gestor não precise varrer a matriz Meta por Meta
 * para descobrir onde o orçamento está no limite.
 *
 * Não renderiza nada quando não há vermelhos. Uma caixa de alerta vazia e
 * permanente é ruído — e, pior, ensina a ignorar a caixa. Mesma regra do
 * `AlertaAcoesCriticas` do painel do PT físico, de onde vem a forma.
 */
export function AlertaAlocacoesCriticas({ celulas, onSelect }: Props) {
  if (celulas.length === 0) return null;

  return (
    <section
      aria-labelledby="alerta-orcamento-titulo"
      data-testid="orcamento-alerta"
      className="flex flex-col gap-3 rounded-lg border border-error-text bg-error-bg p-4"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-error-text">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2
            id="alerta-orcamento-titulo"
            className="text-sm font-semibold text-error-text"
          >
            Alocações que exigem atenção
            <span className="ml-2 font-normal tabular-nums">
              ({celulas.length})
            </span>
          </h2>
          <p className="text-xs leading-relaxed text-error-text">
            {LIMIAR_ALERTA_PCT}% ou mais do valor aprovado já está comprometido.
            Novas demandas sobre estas rubricas tendem a esbarrar em saldo
            insuficiente.
          </p>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {celulas.map((celula) => {
          const { linha, nivelSemaforo, percentual } = celula;
          return (
            <li key={`${linha.meta.id}-${linha.rubrica.slug}`}>
              {/* Botão de largura total, e não uma <li> com link dentro: a
                  linha inteira é o alvo de clique, e um <button> dá foco por
                  teclado e ativação por Enter/Espaço sem handler extra. */}
              <button
                type="button"
                onClick={() => onSelect(celula)}
                data-testid={`orcamento-alerta-item-${linha.meta.id}-${linha.rubrica.slug}`}
                aria-label={`Meta ${linha.meta.numero}, ${linha.rubrica.nome}: ${formatPercentual(percentual)} do aprovado comprometido. Abrir detalhamento.`}
                className="flex w-full items-center gap-3 rounded-md border border-border bg-surface px-3 py-2.5 text-left transition-colors hover:bg-surface-warm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="shrink-0 text-xs font-medium tabular-nums text-text-muted">
                      Meta {linha.meta.numero} ·
                    </span>
                    <span className="truncate text-sm text-text">
                      {linha.rubrica.nome}
                    </span>
                  </div>

                  <span className="text-xs tabular-nums text-text-muted">
                    {formatCurrencyBRL(linha.valor_comprometido)} comprometidos
                    de {formatCurrencyBRL(linha.valor_aprovado)} aprovados
                    <span className="ml-1 font-medium text-text">
                      ({formatPercentual(percentual)})
                    </span>
                  </span>
                </div>

                <SemaforoBadge
                  nivel={nivelSemaforo}
                  label={labelSemaforoOrcamento(nivelSemaforo)}
                  className="shrink-0"
                />
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-text-muted"
                  aria-hidden
                />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
