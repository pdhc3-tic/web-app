"use client";

import { AlertTriangle } from "lucide-react";
import { LIMIAR_VERMELHO } from "@/app/lib/semaforo";
import { AcaoLinha } from "./AcaoLinha";
import type { AcaoAvaliada } from "./tipos";

type Props = {
  acoes: AcaoAvaliada[];
  onSelect: (item: AcaoAvaliada) => void;
};

/**
 * "Ações que exigem atenção" — RF17.
 *
 * Fica no topo e reúne TODAS as Ações em vermelho, atravessando as Metas: o
 * ponto do requisito é que o gestor não precise expandir Meta por Meta para
 * descobrir onde está o problema.
 *
 * Não renderiza nada quando não há vermelhos. Uma caixa de alerta vazia e
 * permanente é ruído — e, pior, ensina a ignorar a caixa.
 */
export function AlertaAcoesCriticas({ acoes, onSelect }: Props) {
  if (acoes.length === 0) return null;

  const pct = Math.round(LIMIAR_VERMELHO * 100);

  return (
    <section
      aria-labelledby="alerta-acoes-titulo"
      data-testid="painel-alerta"
      className="flex flex-col gap-3 rounded-lg border border-error-text bg-error-bg p-4"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-error-text">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2
            id="alerta-acoes-titulo"
            className="text-sm font-semibold text-error-text"
          >
            Ações que exigem atenção
            <span className="ml-2 tabular-nums font-normal">
              ({acoes.length})
            </span>
          </h2>
          <p className="text-xs leading-relaxed text-error-text">
            Execução abaixo de {pct}% do esperado para o tempo já decorrido do
            período.
          </p>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {acoes.map((item) => (
          <li key={item.acao.id}>
            <AcaoLinha item={item} onSelect={onSelect} mostrarMeta />
          </li>
        ))}
      </ul>
    </section>
  );
}
