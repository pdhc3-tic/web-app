"use client";

import { ChevronRight } from "lucide-react";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { progressoLabel } from "@/app/lib/acoes";
import { formatPercentual } from "@/app/lib/semaforo";
import type { AcaoAvaliada } from "./tipos";

type Props = {
  item: AcaoAvaliada;
  onSelect: (item: AcaoAvaliada) => void;
  /** Exibe "Meta N" na linha — usado no alerta, que mistura Metas. */
  mostrarMeta?: boolean;
};

/**
 * Uma Ação na lista do painel.
 *
 * É um <button> de largura total, e não uma <li> com link dentro: a linha
 * inteira é o alvo de clique exigido pela issue, e um botão dá foco por teclado
 * e ativação por Enter/Espaço sem nenhum handler extra.
 */
export function AcaoLinha({ item, onSelect, mostrarMeta = false }: Props) {
  const { acao, meta, avaliacao } = item;
  const { nivel, realizado, esperado } = avaliacao;
  const contagem = progressoLabel(acao);

  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      data-testid={`painel-acao-${acao.id}`}
      data-nivel={nivel}
      aria-label={`Ação ${acao.numero} – ${acao.descricao}. Abrir detalhe.`}
      className="flex w-full items-center gap-3 rounded-md border border-border bg-surface px-3 py-2.5 text-left transition-colors hover:bg-surface-warm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
    >
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-xs font-medium tabular-nums text-text-muted">
            {mostrarMeta && meta ? `Meta ${meta.numero} · ` : ""}
            {acao.numero}
          </span>
          <span className="truncate text-sm text-text">{acao.descricao}</span>
        </div>

        <div className="flex items-baseline justify-between gap-2 text-xs">
          <span className="tabular-nums text-text-muted">
            {contagem} · {acao.tipo_unidade_display}
          </span>
          {/* Realizado ao lado do esperado: o semáforo é a razão entre os dois,
              e vê-los juntos é o que torna a cor auditável. */}
          <span className="shrink-0 tabular-nums text-text-muted">
            <span className="font-medium text-text">
              {formatPercentual(realizado)}
            </span>{" "}
            de {formatPercentual(esperado)} esperado
          </span>
        </div>

        <ProgressBar
          value={realizado}
          label={`Progresso da Ação ${acao.numero}`}
          valueText={`${contagem} — ${formatPercentual(realizado)} realizado, ${formatPercentual(esperado)} esperado`}
          tone={
            nivel === "vermelho"
              ? "error"
              : nivel === "amarelo"
                ? "warning"
                : realizado !== null && realizado >= 100
                  ? "success"
                  : "primary"
          }
        />
      </div>

      <SemaforoBadge nivel={nivel} className="shrink-0" />
      <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" aria-hidden />
    </button>
  );
}
