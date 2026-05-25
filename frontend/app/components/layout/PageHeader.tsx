"use client";

import { ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

export const PAGE_HEADER_SLOT_ID = "appshell-page-header-slot";

/**
 * Renderiza o conteúdo passado dentro do slot do Header do AppShell via portal.
 * Cada página chama <PageHeader>...</PageHeader> com seu título e ações.
 */
export function PageHeader({ children }: { children: ReactNode }) {
  const [slot, setSlot] = useState<HTMLElement | null>(null);

  useEffect(() => {
    // Mounting do portal precisa de acesso ao DOM, que só existe no client após o
    // primeiro paint. Esse setState é a forma idiomática de saltar de "sem DOM" para
    // "DOM disponível" no primeiro mount do componente.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSlot(document.getElementById(PAGE_HEADER_SLOT_ID));
  }, []);

  if (!slot) return null;
  return createPortal(children, slot);
}
