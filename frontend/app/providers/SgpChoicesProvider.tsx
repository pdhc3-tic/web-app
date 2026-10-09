"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/app/lib/api";
import {
  CHOICES_VAZIOS,
  fetchSgpChoices,
  rotuloDe,
  type ChaveChoice,
  type SgpChoices,
} from "@/app/lib/choices";
import { qk } from "@/app/lib/queryKeys";

type EstadoChoices = {
  choices: SgpChoices;
  status: "carregando" | "ok" | "erro";
  erro: string | null;
  recarregar: () => void;
};

const SgpChoicesContext = createContext<EstadoChoices>({
  choices: CHOICES_VAZIOS,
  status: "carregando",
  erro: null,
  recarregar: () => {},
});

/**
 * Choices do SGP para toda a área logada (#272) — SGP, SGD e SCA leem as
 * mesmas listas.
 *
 * Uma requisição por sessão: as listas mudam raramente, então ficam em cache
 * sem expirar (`staleTime: Infinity`) e montar um formulário não refaz a
 * busca. Enquanto carregam, os selects ficam vazios; se a carga falhar, a
 * `ChoicesIndisponiveis` explica o porquê e oferece tentar de novo.
 */
export function SgpChoicesProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: qk.choices,
    queryFn: ({ signal }) => fetchSgpChoices(signal),
    staleTime: Infinity,
    gcTime: Infinity,
  });

  const erro = query.error
    ? query.error instanceof ApiError || query.error instanceof Error
      ? query.error.message
      : "Erro desconhecido."
    : null;

  return (
    <SgpChoicesContext.Provider
      value={{
        choices: query.data ?? CHOICES_VAZIOS,
        status: query.isError ? "erro" : query.data ? "ok" : "carregando",
        erro,
        recarregar: () => void query.refetch(),
      }}
    >
      {children}
    </SgpChoicesContext.Provider>
  );
}

/** As listas (vazias até carregar). */
export function useSgpChoices(): SgpChoices {
  return useContext(SgpChoicesContext).choices;
}

/** Estado da carga — para quem precisa explicar uma falha. */
export function useSgpChoicesEstado(): EstadoChoices {
  return useContext(SgpChoicesContext);
}

/**
 * Rótulo de um valor numa lista dos choices — ex.:
 * `const statusLabel = useRotuloChoice("status_atividade")`. Enquanto as listas
 * carregam, devolve o próprio valor.
 */
export function useRotuloChoice(chave: ChaveChoice): (valor: string | number | null | undefined) => string {
  const opcoes = useSgpChoices()[chave];
  return (valor) => rotuloDe(opcoes, valor);
}
