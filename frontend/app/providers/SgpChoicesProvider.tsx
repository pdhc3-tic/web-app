"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  FALLBACK_CHOICES,
  fetchSgpChoices,
  type SgpChoices,
} from "@/app/lib/choices";

const SgpChoicesContext = createContext<SgpChoices>(FALLBACK_CHOICES);

/**
 * Choices do SGP para toda a árvore do módulo.
 *
 * O valor inicial são os fallbacks locais, então o hook nunca devolve lista
 * vazia e nenhuma tela precisa de estado de carregamento por causa de choice:
 * a UI pinta na hora com as constantes e troca em silêncio se o backend
 * divergir. Uma requisição por navegação ao SGP, compartilhada por todas as
 * telas do módulo.
 */
export function SgpChoicesProvider({ children }: { children: ReactNode }) {
  const [choices, setChoices] = useState<SgpChoices>(FALLBACK_CHOICES);

  useEffect(() => {
    const controller = new AbortController();
    fetchSgpChoices(controller.signal).then((fetched) => {
      if (!controller.signal.aborted) setChoices(fetched);
    });
    return () => controller.abort();
  }, []);

  return (
    <SgpChoicesContext.Provider value={choices}>
      {children}
    </SgpChoicesContext.Provider>
  );
}

/**
 * Choices do SGP. Fora do provider devolve os fallbacks locais em vez de
 * lançar — um select com a lista espelhada é melhor que uma tela quebrada.
 */
export function useSgpChoices(): SgpChoices {
  return useContext(SgpChoicesContext);
}
