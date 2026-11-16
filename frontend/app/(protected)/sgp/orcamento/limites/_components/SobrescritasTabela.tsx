"use client";

import { formatCurrencyBRL } from "@/app/lib/format";
import { valorNumerico } from "@/app/lib/orcamento";
import type { LimiteGasto } from "@/app/lib/limites";
import { PrecedenciaSelo } from "./PrecedenciaSelo";

type Props = {
  linhas: LimiteGasto[];
  editavel: boolean;
  onAlterar: (limite: LimiteGasto) => void;
};

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-top";

/**
 * Aba "Sobrescritas individuais" (#400): as linhas individuais do período —
 * as que a UGP definiu (sobrescritas) e as que nasceram do padrão do perfil na
 * primeira reserva (herdadas). O selo diz qual das duas vale para a pessoa.
 */
export function SobrescritasTabela({ linhas, editavel, onAlterar }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm" data-testid="limites-sobrescritas">
        <thead className="border-b border-border bg-surface-muted/50">
          <tr>
            <th className={TH}>Pessoa</th>
            <th className={TH}>Rubrica</th>
            <th className={TH}>Origem</th>
            <th className={`${TH} text-right`}>Limite</th>
            <th className={`${TH} text-right`}>Usado</th>
            <th className={`${TH} text-right`}>Saldo</th>
            <th className={TH}>Justificativa</th>
            {editavel && <th className={TH}><span className="sr-only">Ações</span></th>}
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => {
            const usado = valorNumerico(l.valor_comprometido) + valorNumerico(l.valor_executado);
            const saldo = valorNumerico(l.saldo_disponivel);
            return (
              <tr
                key={l.id}
                className="border-b border-border last:border-b-0"
                data-testid={`limites-sobrescrita-${l.id}`}
              >
                <td className={`${TD} font-medium text-text`}>{l.user_nome ?? `#${l.user}`}</td>
                <td className={`${TD} text-text`}>{l.rubrica_nome}</td>
                <td className={TD}>
                  <PrecedenciaSelo limite={l} />
                </td>
                <td className={`${TD} text-right tabular-nums text-text`}>{formatCurrencyBRL(l.valor_limite)}</td>
                <td
                  className={`${TD} text-right tabular-nums text-text-muted`}
                  title="Comprometido + executado no período"
                >
                  {formatCurrencyBRL(usado)}
                </td>
                <td className={`${TD} text-right tabular-nums ${saldo < 0 ? "text-error-text" : "text-text"}`}>
                  {formatCurrencyBRL(saldo)}
                </td>
                <td className={`${TD} max-w-xs text-xs text-text-muted`}>
                  <span className="line-clamp-2" title={l.justificativa || undefined}>
                    {l.justificativa || "—"}
                  </span>
                </td>
                {editavel && (
                  <td className={`${TD} text-right`}>
                    <button
                      type="button"
                      onClick={() => onAlterar(l)}
                      className="text-xs text-primary hover:underline focus-visible:outline-2 focus-visible:outline-primary"
                      data-testid="limites-sobrescrita-alterar"
                    >
                      Alterar
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
