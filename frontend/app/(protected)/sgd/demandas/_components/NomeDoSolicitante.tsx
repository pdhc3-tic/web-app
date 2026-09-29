import type { Demanda } from "@/app/lib/demandas";

/**
 * Quem abriu a demanda. O `DemandSerializer` ainda devolve só o id do
 * solicitante (docs/pendencias-backend-sprint-10.md, item 12): até o nome
 * chegar, a tela diz o id em vez de inventar um nome.
 */
export function NomeDoSolicitante({ demanda }: { demanda: Demanda }) {
  if (demanda.solicitante_nome) return <>{demanda.solicitante_nome}</>;
  return (
    <span title="O nome do solicitante ainda não é enviado pela API.">
      Usuário #{demanda.solicitante}
    </span>
  );
}
