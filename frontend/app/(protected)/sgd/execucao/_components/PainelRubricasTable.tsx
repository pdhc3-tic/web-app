"use client";

import { useMemo } from "react";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  formatPercentual,
  type FaixaSemaforo,
  type LinhaPainelRubrica,
} from "@/app/lib/execucaoSgd";

/**
 * Cores do semáforo 70/90. A #297 pede a cor de acento do SGD (Terracota PDHC)
 * para o estado de atenção; vermelho e verde seguem a paleta semântica.
 */
const ESTILO_FAIXA: Record<FaixaSemaforo, { rotulo: string; badge: string; ponto: string }> = {
  vermelho: {
    rotulo: "Vermelho",
    badge: "border-error-text bg-error-bg text-error-text",
    ponto: "bg-error-text",
  },
  amarelo: {
    rotulo: "Amarelo",
    badge: "border-accent-terracota bg-accent-terracota/10 text-accent-terracota",
    ponto: "bg-accent-terracota",
  },
  verde: {
    rotulo: "Verde",
    badge: "border-success-text bg-success-bg text-success-text",
    ponto: "bg-success-text",
  },
};

/**
 * A faixa e o percentual são os do backend (comprometido sobre o aprovado, com
 * os limiares configurados). Rubrica sem verba alocada no recorte não tem
 * semáforo: o backend devolve "verde" com 0%, o que esconderia a falta de teto.
 */
function SemaforoRubricaBadge({ linha }: { linha: LinhaPainelRubrica }) {
  const semVerba =
    Number(linha.executado || 0) + Number(linha.disponivel || 0) === 0 &&
    Number(linha.percentual_execucao || 0) === 0;

  if (semVerba) {
    return (
      <span
        data-testid="semaforo-rubrica"
        data-nivel="sem-teto"
        className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-neutral-text bg-neutral-bg px-2.5 py-0.5 text-2xs font-medium text-neutral-text"
      >
        Sem teto
      </span>
    );
  }

  const estilo = ESTILO_FAIXA[linha.faixa];
  return (
    <span
      data-testid="semaforo-rubrica"
      data-nivel={linha.faixa}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-2xs font-semibold ${estilo.badge}`}
    >
      <span className={`h-2 w-2 rounded-full ${estilo.ponto}`} aria-hidden="true" />
      <span>
        {estilo.rotulo} ({formatPercentual(linha.percentual_execucao)})
      </span>
    </span>
  );
}

export function PainelRubricasTable({
  linhas,
}: {
  linhas: LinhaPainelRubrica[];
}) {
  const totais = useMemo(() => {
    return linhas.reduce(
      (acc, l) => ({
        solicitado: acc.solicitado + Number(l.solicitado || 0),
        autorizado: acc.autorizado + Number(l.autorizado || 0),
        executado: acc.executado + Number(l.executado || 0),
        disponivel: acc.disponivel + Number(l.disponivel || 0),
      }),
      { solicitado: 0, autorizado: 0, executado: 0, disponivel: 0 },
    );
  }, [linhas]);

  if (linhas.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center text-sm text-text-muted">
        Nenhuma rubrica encontrada para os filtros selecionados.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm" data-testid="tabela-painel-rubricas">
          <thead className="border-b border-border bg-surface-muted/50 text-xs font-semibold uppercase tracking-wider text-text-muted">
            <tr>
              <th scope="col" className="px-4 py-3">Rubrica</th>
              <th scope="col" className="px-4 py-3 text-right">Solicitado</th>
              <th scope="col" className="px-4 py-3 text-right">Autorizado</th>
              <th scope="col" className="px-4 py-3 text-right">Executado</th>
              <th scope="col" className="px-4 py-3 text-right">Disponível</th>
              <th scope="col" className="px-4 py-3 text-center">Semáforo (70/90)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {linhas.map((linha) => (
              <tr
                key={linha.rubrica_id}
                className="transition-colors hover:bg-surface-warm/40"
                data-testid={`rubrica-linha-${linha.rubrica_slug}`}
              >
                <td className="px-4 py-3 font-medium text-text">
                  {linha.rubrica_nome}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text">
                  {formatCurrencyBRL(linha.solicitado)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text">
                  {formatCurrencyBRL(linha.autorizado)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text">
                  {formatCurrencyBRL(linha.executado)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums font-medium text-text">
                  {formatCurrencyBRL(linha.disponivel)}
                </td>
                <td className="px-4 py-3 text-center">
                  <SemaforoRubricaBadge linha={linha} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t-2 border-border bg-surface-muted/60 font-semibold text-text">
            <tr>
              <th scope="row" className="px-4 py-3">Total Consolidado</th>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCurrencyBRL(totais.solicitado)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCurrencyBRL(totais.autorizado)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCurrencyBRL(totais.executado)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCurrencyBRL(totais.disponivel)}
              </td>
              <td className="px-4 py-3 text-center text-xs text-text-muted">
                —
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
