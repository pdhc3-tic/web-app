import { useQuery } from "@tanstack/react-query";
import { qk } from "@/app/lib/queryKeys";
import { listTiposSolicitacao } from "@/app/lib/tiposSolicitacao";

/**
 * O catálogo de tipos de solicitação (#365), ativos e inativos, na ordem
 * cadastrada. O formulário oferece só os ativos, mas precisa do schema de um
 * tipo desativado para editar uma solicitação que já o usa.
 */
export function useTiposSolicitacao() {
  return useQuery({
    queryKey: qk.configSgd.tiposSolicitacao,
    queryFn: ({ signal }) => listTiposSolicitacao({ apenasAtivos: false }, signal),
    staleTime: 5 * 60_000,
  });
}
