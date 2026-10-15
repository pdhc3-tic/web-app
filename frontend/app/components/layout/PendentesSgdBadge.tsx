"use client";

import { useContagemFila } from "@/app/lib/hooks/useFilaDemandas";

/** "1 pendente" / "3 pendentes" — o rótulo acessível do badge. */
export function rotuloPendentes(total: number): string {
  return `${total} pendente${total === 1 ? "" : "s"}`;
}

/**
 * Badge "N pendentes" do SGD na sidebar (#296): a contagem da fila
 * "Aguardando minha ação" do perfil logado. Some quando não há pendência —
 * e para quem não decide sobre demandas.
 */
export function PendentesSgdBadge({ className }: { className: string }) {
  const { data } = useContagemFila();
  const total = data?.total ?? 0;
  if (total <= 0) return null;

  const rotulo = rotuloPendentes(total);
  return (
    <span className={className} aria-label={rotulo} title={rotulo} data-testid="sidebar-badge-sgd">
      {total}
    </span>
  );
}
