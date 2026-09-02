"use client";

import { useState } from "react";
import { AlertTriangle, KeyRound } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { ApiError } from "@/app/lib/api";
import {
  reativarAcesso,
  revogarAcesso,
  type AcessoResponse,
} from "@/app/lib/users";

export type AcessoModo = "revogar" | "reativar";

/**
 * As duas confirmações compartilham o mesmo componente porque são dois estados
 * da MESMA ação — o que muda é a copy, o ícone, a variante do botão e qual
 * endpoint chamar. Duplicar em dois arquivos deixaria duas cópias da estrutura
 * do SlideOver para manter em sincronia.
 */
const CONFIG = {
  revogar: {
    title: "Revogar acesso",
    confirmLabel: "Revogar acesso",
    confirmVariant: "danger" as const,
    tone: "bg-error-bg text-error-text",
    Icon: AlertTriangle,
    pergunta: "Revogar o acesso de",
    // A consequência é o ponto da confirmação: o wipe não é imediato, acontece
    // no próximo sync — enquanto o encerramento das sessões é agora.
    consequencia:
      "No próximo sync do dispositivo, o app SCA apagará todos os dados locais do técnico. As sessões ativas são encerradas imediatamente e ele não conseguirá mais entrar no aplicativo.",
    erroFallback: "Não foi possível revogar o acesso. Tente novamente.",
  },
  reativar: {
    title: "Reativar acesso",
    confirmLabel: "Reativar acesso",
    confirmVariant: "primary" as const,
    tone: "bg-warning-bg text-warning-text",
    Icon: KeyRound,
    pergunta: "Reativar o acesso de",
    consequencia:
      "O técnico precisará fazer um novo login completo no app SCA: as sessões anteriores foram invalidadas e os dados locais do dispositivo já foram apagados.",
    erroFallback: "Não foi possível reativar o acesso. Tente novamente.",
  },
};

type Props = {
  open: boolean;
  onClose: () => void;
  modo: AcessoModo;
  /** `null` enquanto o diálogo está fechado. */
  tecnicoId: number | null;
  /** Nome exibido na pergunta. */
  tecnicoNome: string;
  /** Chamado após o backend confirmar, com a resposta da ação. */
  onConfirmado: (id: number, res: AcessoResponse) => void;
};

/**
 * Confirmação de revogação / reativação de acesso ao app SCA.
 *
 * Segue o padrão dos diálogos de confirmação da casa (RemoverMembroDialog):
 * SlideOver com os botões no prop `footer` — nunca inline no corpo —, o padding
 * aplicado aqui pelo chamador (`px-4 py-6`) e o estado `saving` vivendo neste
 * componente, que é quem renderiza o SlideOver.
 */
export function AcessoDialog({
  open,
  onClose,
  modo,
  tecnicoId,
  tecnicoNome,
  onConfirmado,
}: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cfg = CONFIG[modo];
  const { Icon } = cfg;

  async function handleConfirm() {
    if (saving || tecnicoId == null) return;
    setError(null);
    setSaving(true);
    try {
      const res =
        modo === "revogar"
          ? await revogarAcesso(tecnicoId)
          : await reativarAcesso(tecnicoId);
      onConfirmado(tecnicoId, res);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : cfg.erroFallback);
    } finally {
      setSaving(false);
    }
  }

  function handleClose() {
    if (saving) return;
    setError(null);
    onClose();
  }

  return (
    <SlideOver
      open={open}
      onClose={handleClose}
      title={cfg.title}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            onClick={handleClose}
            disabled={saving}
            data-testid="acesso-dialog-cancelar"
          >
            Cancelar
          </Button>
          <Button
            variant={cfg.confirmVariant}
            onClick={handleConfirm}
            loading={saving}
            data-testid="acesso-dialog-confirmar"
          >
            {cfg.confirmLabel}
          </Button>
        </div>
      }
    >
      <div
        data-testid={`acesso-dialog-${modo}`}
        className="flex flex-col gap-4 px-4 py-6"
      >
        <div className="flex items-start gap-3">
          <span
            className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${cfg.tone}`}
          >
            <Icon className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text">
              {cfg.pergunta}{" "}
              <span className="font-semibold">{tecnicoNome}</span>?
            </p>
            <p className="mt-1 text-sm leading-relaxed text-text-muted">
              {cfg.consequencia}
            </p>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
          >
            {error}
          </div>
        )}
      </div>
    </SlideOver>
  );
}
