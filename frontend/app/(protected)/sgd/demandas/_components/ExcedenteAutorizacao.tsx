"use client";

import Link from "next/link";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import type { Demanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { useAlocacoesDeOrigem } from "@/app/lib/hooks/useAlocacoesDeOrigem";

/** A alocação escolhida e a rubrica dela: o excedente só pesa nessa rubrica. */
export type OrigemExcedente = { id: string; rubricaSlug: string };

/**
 * Autorização com excedente (#363): a UGP marca o excedente e escolhe a
 * alocação estadual ou nacional que o cobre, com justificativa. O backend
 * remaneja dela na própria decisão, sem elevar o limite individual.
 */
export function ExcedenteAutorizacao({
  demanda,
  ativo,
  onAtivo,
  origem,
  onOrigem,
  justificativa,
  onJustificativa,
}: {
  demanda: Demanda;
  ativo: boolean;
  onAtivo: (ativo: boolean) => void;
  origem: OrigemExcedente | null;
  onOrigem: (origem: OrigemExcedente | null) => void;
  justificativa: string;
  onJustificativa: (justificativa: string) => void;
}) {
  const rubricas = [...new Set(demanda.solicitacoes.map((s) => s.rubrica_slug))];
  const { alocacoes, carregando } = useAlocacoesDeOrigem(ativo ? demanda.activity : null, rubricas);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border px-3 py-2.5" data-testid="excedente">
      <label className="flex items-center gap-2 text-sm font-medium text-text">
        <input
          type="checkbox"
          checked={ativo}
          onChange={(e) => onAtivo(e.target.checked)}
          data-testid="excedente-ativo"
        />
        Autorizar excedente
      </label>
      {ativo && (
        <>
          <p className="text-xs text-text-muted" data-testid="excedente-aviso">
            O excedente vale só para esta solicitação e não aumenta o limite individual. Para elevar o limite, use o
            fluxo de{" "}
            <Link href="/sgd/remanejamentos" className="font-medium text-primary underline hover:no-underline">
              recurso extra
            </Link>
            .
          </p>
          <Select
            id="excedente-origem"
            label="Origem do excedente"
            required
            disabled={carregando || alocacoes.length === 0}
            placeholder={carregando ? "Carregando alocações…" : "Selecione a alocação"}
            options={alocacoes.map((a) => ({
              value: String(a.id),
              label: `${a.rubrica.nome} · ${a.estado?.nome ?? "Nacional"} — saldo ${formatCurrencyBRL(a.saldo_disponivel)}`,
            }))}
            value={origem?.id ?? ""}
            onChange={(id) => {
              const alocacao = alocacoes.find((a) => String(a.id) === id);
              onOrigem(alocacao ? { id, rubricaSlug: alocacao.rubrica.slug } : null);
            }}
            helperText={
              !carregando && alocacoes.length === 0
                ? "Nenhuma alocação estadual ou nacional destas rubricas na Meta da atividade."
                : undefined
            }
          />
          <Textarea
            id="excedente-justificativa"
            label="Justificativa do excedente"
            required
            value={justificativa}
            onChange={(e) => onJustificativa(e.target.value)}
          />
        </>
      )}
    </div>
  );
}
