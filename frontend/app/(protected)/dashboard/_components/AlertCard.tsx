"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

export type CardState =
  | { phase: "loading" }
  | { phase: "ok"; count: number }
  | { phase: "error" };

/**
 * Card de alerta do dashboard (#236): contagem, "Nenhuma pendência" ou falha,
 * sempre com o link para a listagem filtrada pelo mesmo critério da contagem.
 */
export function AlertCard({
  title,
  description,
  state,
  href,
}: {
  title: string;
  description: string;
  state: CardState;
  href: string;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
          {title}
        </p>
        <p className="mt-1 text-xs text-text-muted">{description}</p>
      </div>

      {state.phase === "loading" && (
        <div className="h-8 w-16 animate-pulse rounded bg-surface-muted" />
      )}

      {state.phase === "error" && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Não foi possível carregar
        </div>
      )}

      {state.phase === "ok" && state.count === 0 && (
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm text-success-text">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Nenhuma pendência
          </div>
          <Link
            href={href}
            className="text-xs font-medium text-primary underline-offset-2 hover:underline"
          >
            Ver listagem →
          </Link>
        </div>
      )}

      {state.phase === "ok" && state.count > 0 && (
        <div className="flex items-end justify-between gap-2">
          <span className="text-3xl font-semibold tabular-nums text-error-text">
            {state.count}
          </span>
          <Link
            href={href}
            className="text-xs font-medium text-primary underline-offset-2 hover:underline"
          >
            Ver listagem →
          </Link>
        </div>
      )}
    </div>
  );
}
