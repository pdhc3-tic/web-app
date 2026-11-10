"use client";

import { Info, MapPinOff } from "lucide-react";
import type { Demanda } from "@/app/lib/demandas";

type ComAbrangencia = Pick<
  Demanda,
  "estado_sigla" | "territorio_nome" | "atividade_fora_do_territorio"
>;

/**
 * Selo curto para a listagem e o cabeçalho: a atividade é em outro estado
 * que não o da demanda (#361). Só sinaliza — a demanda segue o fluxo normal.
 */
export function SeloForaDoTerritorio({ demanda }: { demanda: ComAbrangencia }) {
  if (!demanda.atividade_fora_do_territorio) return null;
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-info-text"
      title="A atividade acontece em outro estado; a demanda segue o território de quem a criou."
      data-testid="selo-fora-do-territorio"
    >
      <MapPinOff className="h-3.5 w-3.5 shrink-0" aria-hidden />
      Atividade fora do território
    </span>
  );
}

/**
 * Aviso informativo, não bloqueante (#361, decisão 1 do §3): a demanda é
 * analisada pelo Articulador do estado de quem a criou e consome o saldo do
 * território dele, onde quer que a atividade aconteça.
 *
 * O estado da atividade não vem na demanda (`contexto` traz só o município),
 * por isso o texto diz "outro estado" em vez da sigla — pendência no
 * docs/pendencias-backend-sprint-12a.md.
 */
export function AvisoForaDoTerritorio({ demanda }: { demanda: ComAbrangencia }) {
  if (!demanda.atividade_fora_do_territorio || !demanda.estado_sigla) return null;
  const saldo = demanda.territorio_nome
    ? `o saldo do seu território (${demanda.territorio_nome})`
    : `o saldo de ${demanda.estado_sigla}`;
  return (
    <p
      role="status"
      className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text"
      data-testid="aviso-fora-do-territorio"
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>
        A atividade é em outro estado. A demanda será analisada pelo Articulador
        de {demanda.estado_sigla} e usará {saldo}.
      </span>
    </p>
  );
}
