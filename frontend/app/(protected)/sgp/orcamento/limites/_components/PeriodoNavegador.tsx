"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { formatDate } from "@/app/lib/datetime";
import type { Periodo } from "@/app/lib/limites";

type Props = {
  periodo: Periodo;
  vigente: boolean;
  /** Na vigência do TED há um período só: sem setas. */
  navegavel: boolean;
  podeAvancar: boolean;
  onAnterior: () => void;
  onSeguinte: () => void;
  onVoltarAoVigente: () => void;
};

const BOTAO =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-border text-text-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-primary";

/**
 * Período dos limites exibidos (#400), pelo `budget_limit_period`. Só o
 * vigente aceita alterações; os outros ficam para consulta.
 */
export function PeriodoNavegador({
  periodo,
  vigente,
  navegavel,
  podeAvancar,
  onAnterior,
  onSeguinte,
  onVoltarAoVigente,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3" data-testid="limites-periodo">
      {navegavel && (
        <button
          type="button"
          className={BOTAO}
          onClick={onAnterior}
          aria-label="Período anterior"
          data-testid="limites-periodo-anterior"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden />
        </button>
      )}
      <div className="min-w-0">
        <p className="text-sm font-semibold text-text" data-testid="limites-periodo-rotulo">
          {periodo.rotulo}
        </p>
        {navegavel && (
          <p className="text-xs tabular-nums text-text-muted">
            {formatDate(periodo.inicio)} a {formatDate(periodo.fim)}
          </p>
        )}
      </div>
      {navegavel && (
        <button
          type="button"
          className={BOTAO}
          onClick={onSeguinte}
          disabled={!podeAvancar}
          aria-label="Período seguinte"
          data-testid="limites-periodo-seguinte"
        >
          <ChevronRight className="h-4 w-4" aria-hidden />
        </button>
      )}
      {vigente ? (
        <span className="rounded-full bg-success-bg px-2 py-0.5 text-2xs font-medium text-success-text">
          Vigente
        </span>
      ) : (
        <>
          <span
            className="rounded-full bg-surface-muted px-2 py-0.5 text-2xs font-medium text-text-muted"
            data-testid="limites-somente-leitura"
          >
            Somente consulta
          </span>
          <button
            type="button"
            onClick={onVoltarAoVigente}
            className="text-xs text-primary hover:underline"
            data-testid="limites-periodo-vigente"
          >
            Voltar ao período vigente
          </button>
        </>
      )}
    </div>
  );
}
