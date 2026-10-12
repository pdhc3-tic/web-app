import type { Demanda } from "@/app/lib/demandas";

/** Quem abriu a demanda (`solicitante_nome` do `DemandSerializer`). */
export function NomeDoSolicitante({ demanda }: { demanda: Demanda }) {
  return <>{demanda.solicitante_nome}</>;
}
