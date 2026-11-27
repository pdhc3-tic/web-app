"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { formatCurrencyBRL } from "@/app/lib/format";
import { valorNumerico } from "@/app/lib/orcamento";
import type { LinhaDotacao } from "./tipos";

export type ConfirmacaoDotacao = {
  linha: LinhaDotacao;
  /** Valor pretendido, já normalizado para decimal ("1234.56"). */
  valor: string;
};

type Props = {
  confirmacao: ConfirmacaoDotacao | null;
  onCancel: () => void;
  onConfirm: () => void;
  salvando: boolean;
};

/**
 * Confirmação antes de gravar a dotação, no mesmo formato da
 * `ConfirmarDistribuicaoDialog`: SlideOver, resumo do que será gravado e a
 * diferença quando é ajuste.
 */
export function ConfirmarDotacaoDialog({ confirmacao, onCancel, onConfirm, salvando }: Props) {
  const pool = confirmacao?.linha.pool ?? null;
  const atual = pool ? valorNumerico(pool.valor_aprovado) : 0;
  const novo = confirmacao ? valorNumerico(confirmacao.valor) : 0;
  const delta = novo - atual;
  const ehAjuste = pool !== null;

  return (
    <SlideOver
      open={confirmacao !== null}
      onClose={onCancel}
      title={ehAjuste ? "Ajustar dotação nacional" : "Lançar dotação nacional"}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={salvando} data-testid="dotacao-cancelar">
            Cancelar
          </Button>
          <Button onClick={onConfirm} loading={salvando} data-testid="dotacao-confirmar">
            {ehAjuste ? "Confirmar ajuste" : "Confirmar lançamento"}
          </Button>
        </div>
      }
    >
      {confirmacao === null ? null : (
        <div className="flex flex-col gap-6 px-4 py-4" data-testid="dotacao-confirmacao">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning-bg text-warning-text">
              <AlertTriangle className="h-5 w-5" aria-hidden />
            </span>
            <p className="min-w-0 text-sm leading-relaxed text-text-muted">
              A dotação nacional é o teto de tudo o que a rubrica distribui aos estados e territórios. O
              valor fica registrado em seu nome e pode ser ajustado depois, mas{" "}
              <strong className="text-text">não pode ser excluído</strong> por aqui.
            </p>
          </div>

          <section>
            <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
              O que será gravado
            </h3>
            <DefinitionList
              items={[
                { label: "Rubrica", value: confirmacao.linha.rubrica.nome },
                { label: "Nível", value: "Nacional" },
              ]}
            />
          </section>

          <section>
            <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">Valor</h3>
            <DefinitionList
              items={[
                ...(ehAjuste ? [{ label: "Dotação hoje", value: formatCurrencyBRL(atual) }] : []),
                {
                  label: ehAjuste ? "Passará a ser" : "Será lançado",
                  value: <strong className="text-text">{formatCurrencyBRL(novo)}</strong>,
                },
                ...(ehAjuste
                  ? [
                      {
                        label: "Diferença",
                        value: (
                          <span className={delta < 0 ? "text-error-text" : "text-success-text"}>
                            {delta >= 0 ? "+" : "−"}
                            {formatCurrencyBRL(Math.abs(delta))}
                          </span>
                        ),
                      },
                    ]
                  : []),
              ]}
            />
          </section>
        </div>
      )}
    </SlideOver>
  );
}
