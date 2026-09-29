"use client";

import { useId, useState, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";

export type ConfirmationDrawerProps = {
  open: boolean;
  title: string;
  /** O que acontece ao confirmar — dito em frase, não em "Tem certeza?". */
  description: ReactNode;
  /** Rótulo do botão destrutivo: o verbo da ação ("Recusar demanda"). */
  confirmLabel: string;
  /** Rótulo do botão que desiste: o que se mantém ("Manter demanda"). */
  keepLabel: string;
  justificativaLabel?: string;
  /** Recebe a justificativa já sem espaços nas pontas. */
  onConfirm: (justificativa: string) => Promise<void>;
  onClose: () => void;
  "data-testid"?: string;
};

/**
 * Confirmação de ação de alto impacto (#296): justificativa obrigatória e
 * botões que dizem o que fazem — nunca "Sim/Não".
 *
 * O erro da API aparece dentro do drawer, que continua aberto para corrigir e
 * tentar de novo.
 */
export function ConfirmationDrawer({
  open,
  title,
  description,
  confirmLabel,
  keepLabel,
  justificativaLabel = "Justificativa",
  onConfirm,
  onClose,
  "data-testid": testId,
}: ConfirmationDrawerProps) {
  const campoId = useId();
  const [justificativa, setJustificativa] = useState("");
  const [erroCampo, setErroCampo] = useState<string | null>(null);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function fechar() {
    if (enviando) return;
    setJustificativa("");
    setErroCampo(null);
    setErroGeral(null);
    onClose();
  }

  async function confirmar() {
    const texto = justificativa.trim();
    if (!texto) {
      setErroCampo("A justificativa é obrigatória.");
      return;
    }
    setEnviando(true);
    setErroGeral(null);
    try {
      await onConfirm(texto);
      setJustificativa("");
    } catch (e) {
      setErroGeral(e instanceof Error ? e.message : "Não foi possível concluir a ação.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={fechar}
      title={title}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={fechar} disabled={enviando}>
            {keepLabel}
          </Button>
          <Button
            variant="danger"
            onClick={confirmar}
            loading={enviando}
            data-testid={testId ? `${testId}-confirmar` : undefined}
          >
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-4 py-6" data-testid={testId}>
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0 text-sm leading-relaxed text-text-muted">{description}</div>
        </div>

        <Textarea
          id={campoId}
          label={justificativaLabel}
          required
          rows={4}
          value={justificativa}
          onChange={(e) => {
            setJustificativa(e.target.value);
            setErroCampo(null);
          }}
          error={erroCampo ?? undefined}
        />

        {erroGeral && (
          <p role="alert" className="text-sm text-error-text">
            {erroGeral}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
