"use client";

import { useState } from "react";
import { Copy, KeyRound } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";

type Props = {
  /** Token em claro. `null` = diálogo fechado. */
  token: string | null;
  onClose: () => void;
};

/**
 * Diálogo que apresenta o token recém-regenerado (#143 AC-4). Exibe o valor
 * em claro apenas nesta janela — depois de fechar, não há como recuperar.
 * O botão "Fechar" força um `confirm()` para evitar fechamento acidental
 * antes de copiar.
 */
export function NovoTokenDialog({ token, onClose }: Props) {
  const { showToast } = useToast();
  const [copiado, setCopiado] = useState(false);

  async function copiar() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopiado(true);
      showToast("Token copiado.");
    } catch {
      showToast("Não foi possível copiar. Copie manualmente.", "error");
    }
  }

  function handleClose() {
    if (!copiado) {
      const ok = window.confirm(
        "Você ainda não copiou o token. Ele não poderá ser recuperado depois. Fechar mesmo assim?",
      );
      if (!ok) return;
    }
    setCopiado(false);
    onClose();
  }

  return (
    <SlideOver
      open={token !== null}
      onClose={handleClose}
      title="Novo token gerado"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            onClick={handleClose}
            data-testid="powerbi-novo-token-fechar"
          >
            Fechar
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 px-4 py-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted">
            <KeyRound className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text">
              Copie o token agora.
            </p>
            <p className="mt-1 text-sm leading-relaxed text-text-muted">
              Este é o único momento em que o valor completo é exibido. Depois
              de fechar este diálogo, o backend só devolve a versão mascarada.
            </p>
          </div>
        </div>

        <div className="flex items-stretch gap-2">
          <code
            data-testid="powerbi-novo-token"
            className="flex-1 break-all rounded-md border border-border bg-surface-muted px-3 py-2 font-mono text-xs text-text"
          >
            {token ?? ""}
          </code>
          <Button
            variant="secondary"
            leftIcon={<Copy className="h-4 w-4" />}
            onClick={copiar}
            data-testid="powerbi-novo-token-copiar"
          >
            Copiar
          </Button>
        </div>
      </div>
    </SlideOver>
  );
}
