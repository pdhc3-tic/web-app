"use client";

import { useMemo } from "react";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  calcularSemaforoRubrica,
  type LinhaPainelRubrica,
  type SemaforoRubricaNivel,
} from "@/app/lib/execucaoSgd";

function SemaforoRubricaBadge({
  nivel,
  percentual,
}: {
  nivel: SemaforoRubricaNivel;
  percentual: number | null;
}) {
  const pctTexto = percentual !== null ? `${percentual.toFixed(1)}%` : "—";

  if (nivel === "vermelho") {
    return (
      <span
        data-testid="semaforo-rubrica"
        data-nivel="vermelho"
        className="inline-flex items-center gap-1.5 rounded-full border border-error-text bg-error-bg px-2.5 py-0.5 text-2xs font-semibold text-error-text"
      >
        <span className="h-2 w-2 rounded-full bg-error-text" aria-hidden="true" />
        <span>Vermelho ({pctTexto})</span>
      </span>
    );
  }

  if (nivel === "amarelo") {
    return (
      <span
        data-testid="semaforo-rubrica"
        data-nivel="amarelo"
        style={{
          backgroundColor: "color-mix(in srgb, #b05a2f 12%, transparent)",
          color: "#b05a2f",
          borderColor: "#b05a2f",
        }}
        className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-2xs font-semibold"
      >
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: "#b05a2f" }}
          aria-hidden="true"
        />
        <span>Amarelo ({pctTexto})</span>
      </span>
    );
  }

  if (nivel === "verde") {
    return (
      <span
        data-testid="semaforo-rubrica"
        data-nivel="verde"
        className="inline-flex items-center gap-1.5 rounded-full border border-success-text bg-success-bg px-2.5 py-0.5 text-2xs font-semibold text-success-text"
      >
        <span className="h-2 w-2 rounded-full bg-success-text" aria-hidden="true" />
        <span>Verde ({pctTexto})</span>
      </span>
    );
  }

  return (
    <span
      data-testid="semaforo-rubrica"
      data-nivel="sem-dado"
      className="inline-flex items-center gap-1.5 rounded-full border border-neutral-text border-dashed bg-neutral-bg px-2.5 py-0.5 text-2xs font-medium text-neutral-text"
    >
      <span>Sem teto</span>
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
            {linhas.map((linha) => {
              const semaforo = calcularSemaforoRubrica(linha);
              return (
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
                    <SemaforoRubricaBadge
                      nivel={semaforo.nivel}
                      percentual={semaforo.percentual}
                    />
                  </td>
                </tr>
              );
            })}
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
