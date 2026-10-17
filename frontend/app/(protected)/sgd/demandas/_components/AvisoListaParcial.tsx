"use client";

import type { ListaDemandas } from "@/app/lib/demandas";

/**
 * A listagem de demandas é paginada no backend e as telas pedem uma página
 * cheia (200). Se houver mais, avisa em vez de esconder o resto em silêncio.
 */
export function AvisoListaParcial({ lista }: { lista: ListaDemandas | undefined }) {
  if (!lista || lista.total <= lista.demandas.length) return null;
  return (
    <p role="status" className="text-xs text-text-muted" data-testid="demandas-lista-parcial">
      Mostrando {lista.demandas.length} de {lista.total} demandas.
    </p>
  );
}
