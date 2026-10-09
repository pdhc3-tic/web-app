"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { useSgpChoicesEstado } from "@/app/providers/SgpChoicesProvider";

/**
 * Aviso de falha na carga das opções dos formulários (#272). Sem ele, os
 * selects ficariam vazios sem explicação; com ele, o usuário sabe o que houve e
 * pode tentar de novo. Some quando a carga dá certo.
 */
export function ChoicesIndisponiveis() {
  const { status, erro, recarregar } = useSgpChoicesEstado();
  if (status !== "erro") return null;

  return (
    <div
      role="alert"
      data-testid="choices-indisponiveis"
      className="mb-4 flex flex-wrap items-start gap-3 rounded-lg border border-error-text bg-error-bg px-4 py-3 text-sm text-error-text"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="flex-1">
        Não foi possível carregar as opções dos formulários (gênero, tipo de atividade,
        produção e outras). Os campos de seleção ficam vazios até a carga dar certo.
        {erro && <span className="block text-xs opacity-80">{erro}</span>}
      </p>
      <Button size="sm" variant="secondary" onClick={recarregar}>
        Tentar novamente
      </Button>
    </div>
  );
}
