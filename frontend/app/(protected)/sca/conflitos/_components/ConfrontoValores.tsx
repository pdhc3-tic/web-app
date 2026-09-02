"use client";

import { Smartphone, Server } from "lucide-react";
import { formatarValor, type ValorConflito } from "@/app/lib/conflitos";

type Props = {
  valorLocal: ValorConflito;
  valorServidor: ValorConflito;
  /** Realça o lado escolhido enquanto o usuário decide. */
  destaque?: "local" | "servidor" | null;
};

/**
 * Confronto lado a lado do campo em conflito.
 *
 * A comparação é POR CAMPO, e não entre os registros inteiros: o `ConflictLog`
 * guarda `campo`, `valor_local` e `valor_servidor`, e não existe em lugar nenhum
 * um retrato do registro como estava no aparelho. O registro do servidor aparece
 * como contexto ao redor, na tela de detalhe.
 *
 * Os dois lados são neutros de propósito — nenhum é "o errado", e é justamente
 * isso que a pessoa está sendo chamada para decidir.
 */
export function ConfrontoValores({ valorLocal, valorServidor, destaque }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="conflito-confronto">
      <Lado
        icone={<Smartphone className="h-3.5 w-3.5" aria-hidden />}
        titulo="No aparelho"
        legenda="Enviado pela coleta em campo"
        valor={valorLocal}
        testid="conflito-valor-local"
        destacado={destaque === "local"}
      />
      <Lado
        icone={<Server className="h-3.5 w-3.5" aria-hidden />}
        titulo="No servidor"
        legenda="Valor atualmente gravado"
        valor={valorServidor}
        testid="conflito-valor-servidor"
        destacado={destaque === "servidor"}
      />
    </div>
  );
}

function Lado({
  icone,
  titulo,
  legenda,
  valor,
  testid,
  destacado,
}: {
  icone: React.ReactNode;
  titulo: string;
  legenda: string;
  valor: ValorConflito;
  testid: string;
  destacado: boolean;
}) {
  const vazio = valor === null || valor === undefined || valor === "";

  return (
    <div
      data-testid={testid}
      className={`flex flex-col gap-1.5 rounded-lg border p-4 transition-colors ${
        destacado
          ? "border-primary bg-surface shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_12%,transparent)]"
          : "border-border bg-surface"
      }`}
    >
      <span className="inline-flex items-center gap-1.5 text-2xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {icone}
        {titulo}
      </span>
      <span
        className={`break-words text-sm ${vazio ? "italic text-text-muted" : "font-medium text-text"}`}
      >
        {formatarValor(valor)}
      </span>
      <span className="text-xs text-text-muted">{legenda}</span>
    </div>
  );
}
