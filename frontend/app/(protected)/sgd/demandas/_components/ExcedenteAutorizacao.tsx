"use client";

import Link from "next/link";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import type { Demanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { usePoolsDeOrigem } from "@/app/lib/hooks/usePoolsDeOrigem";

/** O pool escolhido e a rubrica dele: o excedente só pesa nessa rubrica. */
export type OrigemExcedente = { id: string; rubricaSlug: string };

/**
 * Autorização com excedente (#363): a UGP marca o excedente e escolhe a
 * pool estadual ou nacional que o cobre, com justificativa. O backend
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
  const { pools, carregando, falhou } = usePoolsDeOrigem(rubricas, ativo);

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
            disabled={carregando || pools.length === 0}
            placeholder={carregando ? "Carregando origens…" : "Selecione a origem"}
            options={pools.map((p) => ({
              value: String(p.id),
              label: `${p.rubrica.nome} · ${p.estado?.nome ?? "Nacional"} — saldo ${formatCurrencyBRL(p.saldo_pool)}`,
            }))}
            value={origem?.id ?? ""}
            onChange={(id) => {
              const pool = pools.find((p) => String(p.id) === id);
              onOrigem(pool ? { id, rubricaSlug: pool.rubrica.slug } : null);
            }}
            helperText={
              falhou
                ? "Não foi possível carregar as origens. Tente de novo."
                : !carregando && pools.length === 0
                  ? "Nenhum pool estadual ou nacional destas rubricas."
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
