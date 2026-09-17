"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { formatCurrencyBRL } from "@/app/lib/format";
import { valorNumerico } from "@/app/lib/orcamento";
import type { Destino } from "./tipos";

export type Confirmacao = {
  destino: Destino;
  /** Valor pretendido, já normalizado para decimal ("1234.56"). */
  valor: string;
  metaLabel: string;
  rubricaLabel: string;
  /** "Estadual" ou "Territorial". */
  nivelLabel: string;
};

type Props = {
  confirmacao: Confirmacao | null;
  onCancel: () => void;
  onConfirm: () => void;
  salvando: boolean;
};

/**
 * Confirmação antes de gravar (§5.3.2).
 *
 * SlideOver e não um modal próprio: é o que `ConfirmarRegeneracaoDialog` já faz
 * para a outra ação destrutiva do sistema, e o design system não tem Dialog.
 *
 * O resumo repete Meta, rubrica, destino e nível porque a tela tem dois selects
 * acima da lista — quem chega aqui depois de mexer nos filtros precisa ver
 * contra o que está gravando, não só quanto.
 */
export function ConfirmarDistribuicaoDialog({
  confirmacao,
  onCancel,
  onConfirm,
  salvando,
}: Props) {
  const atual = confirmacao?.destino.alocacao
    ? valorNumerico(confirmacao.destino.alocacao.valor_alocado)
    : 0;
  const novo = confirmacao ? valorNumerico(confirmacao.valor) : 0;
  const delta = novo - atual;
  const ehAjuste = confirmacao?.destino.alocacao != null;

  return (
    <SlideOver
      open={confirmacao !== null}
      onClose={onCancel}
      title={ehAjuste ? "Ajustar alocação" : "Distribuir orçamento"}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            onClick={onCancel}
            disabled={salvando}
            data-testid="distribuicao-cancelar"
          >
            Cancelar
          </Button>
          <Button
            onClick={onConfirm}
            loading={salvando}
            data-testid="distribuicao-confirmar"
          >
            {ehAjuste ? "Confirmar ajuste" : "Confirmar distribuição"}
          </Button>
        </div>
      }
    >
      {confirmacao === null ? null : (
        <div
          className="flex flex-col gap-6 px-4 py-4"
          data-testid="distribuicao-confirmacao"
        >
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning-bg text-warning-text">
              <AlertTriangle className="h-5 w-5" aria-hidden />
            </span>
            <p className="min-w-0 text-sm leading-relaxed text-text-muted">
              A alocação fica registrada com uma transação em seu nome. Uma vez
              gravada, o valor pode ser ajustado, mas a linha{" "}
              <strong className="text-text">não pode ser excluída</strong>.
            </p>
          </div>

          <section>
            <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
              O que será gravado
            </h3>
            <DefinitionList
              items={[
                { label: "Meta", value: confirmacao.metaLabel },
                { label: "Rubrica", value: confirmacao.rubricaLabel },
                { label: "Destino", value: confirmacao.destino.nome },
                { label: "Nível", value: confirmacao.nivelLabel },
              ]}
            />
          </section>

          <section>
            <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
              Valor
            </h3>
            <DefinitionList
              items={[
                ...(ehAjuste
                  ? [{ label: "Alocado hoje", value: formatCurrencyBRL(atual) }]
                  : []),
                {
                  label: ehAjuste ? "Passará a ser" : "Será alocado",
                  value: (
                    <strong className="text-text">
                      {formatCurrencyBRL(novo)}
                    </strong>
                  ),
                },
                ...(ehAjuste
                  ? [
                      {
                        label: "Diferença",
                        value: (
                          <span
                            className={
                              delta < 0 ? "text-error-text" : "text-success-text"
                            }
                          >
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
