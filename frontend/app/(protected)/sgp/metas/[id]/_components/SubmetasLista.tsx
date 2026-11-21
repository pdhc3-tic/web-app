"use client";

import { formatDate } from "@/app/lib/datetime";
import type { Submeta } from "@/app/lib/submetas";

type Props = {
  submetas: Submeta[];
  /** Quantas Ações cada Submeta tem, pelo id dela. */
  acoesPorSubmeta: Map<number, number>;
};

/**
 * As Submetas da Meta (#431), na ordem do número. Cada linha diz quantas
 * Ações tem, para a hierarquia Meta → Submeta → Ação ficar visível.
 */
export function SubmetasLista({ submetas, acoesPorSubmeta }: Props) {
  return (
    <ul className="divide-y divide-border rounded-lg border border-border bg-surface" data-testid="submetas-lista">
      {submetas.map((s) => {
        const n = acoesPorSubmeta.get(s.id) ?? 0;
        return (
          <li
            key={s.id}
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3"
            data-testid={`submeta-${s.id}`}
          >
            <div className="flex min-w-0 items-baseline gap-3">
              <span className="shrink-0 text-sm font-semibold tabular-nums text-text">{s.numero}</span>
              <span className="truncate text-sm text-text">{s.titulo}</span>
            </div>
            <span className="flex shrink-0 items-center gap-3 text-xs text-text-muted">
              <span className="tabular-nums">
                {formatDate(s.data_inicio)} – {formatDate(s.data_fim)}
              </span>
              <span className="tabular-nums" data-testid={`submeta-${s.id}-acoes`}>
                {n} {n === 1 ? "ação" : "ações"}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
