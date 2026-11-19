"use client";

import { Info, MapPinOff } from "lucide-react";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import type { AbrangenciaPrevia, Articulador, Demanda } from "@/app/lib/demandas";

type ComAbrangencia = Pick<
  Demanda,
  "estado_sigla" | "territorio_nome" | "atividade_fora_do_territorio"
>;

/**
 * Quem analisa a demanda (#361): os Articuladores Estaduais ativos do estado
 * dela, como o backend devolve. `null` na demanda nacional, que não passa por
 * Articulador.
 */
export function rotuloArticuladores(
  estadoSigla: string | null,
  articuladores: Articulador[],
): string | null {
  if (!estadoSigla) return null;
  if (articuladores.length === 0) return `Nenhum Articulador Estadual ativo em ${estadoSigla}`;
  return articuladores.map((a) => a.nome).join(", ");
}

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
 * `ufAtividade` vem do `contexto.municipio_estado_sigla` da demanda, ou do
 * município da atividade escolhida, na prévia antes de criar.
 */
export function AvisoForaDoTerritorio({
  demanda,
  ufAtividade,
}: {
  demanda: ComAbrangencia;
  ufAtividade: string | null;
}) {
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
        A atividade é em {ufAtividade ?? "outro estado"}. A demanda será analisada pelo
        Articulador de {demanda.estado_sigla} e usará {saldo}.
      </span>
    </p>
  );
}

/**
 * Prévia da abrangência no formulário, antes de criar (#361): o território
 * da demanda, quem vai analisá-la e, com atividade de outro estado, o aviso.
 * Tudo como `GET /sgd/demandas/abrangencia/` devolve, pela mesma regra da
 * criação — o front não recalcula nada.
 */
export function PreviaAbrangencia({
  previa,
  ufAtividade,
}: {
  previa: AbrangenciaPrevia;
  ufAtividade: string | null;
}) {
  const comoDemanda: ComAbrangencia = {
    estado_sigla: previa.estado_sigla,
    territorio_nome: previa.territorio?.nome ?? null,
    atividade_fora_do_territorio: previa.atividade_fora_do_territorio,
  };
  const territorio = previa.territorio
    ? previa.estado_sigla
      ? `${previa.territorio.nome} (${previa.estado_sigla})`
      : previa.territorio.nome
    : (previa.estado_sigla ?? "Nacional");
  const analisadaPor = rotuloArticuladores(previa.estado_sigla, previa.articuladores);

  return (
    <div className="flex flex-col gap-3" data-testid="previa-abrangencia">
      <DefinitionList
        items={[
          {
            label: "Território da demanda",
            value: <span data-testid="previa-territorio">{territorio}</span>,
          },
          // Demanda nacional: não passa por Articulador, então a linha some.
          ...(analisadaPor
            ? [
                {
                  label: "Analisada por",
                  value: <span data-testid="previa-articuladores">{analisadaPor}</span>,
                },
              ]
            : []),
        ]}
      />
      <AvisoForaDoTerritorio demanda={comoDemanda} ufAtividade={ufAtividade} />
    </div>
  );
}
