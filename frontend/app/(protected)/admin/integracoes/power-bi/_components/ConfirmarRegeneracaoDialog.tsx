"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";

type Props = {
  open: boolean;
  /** `false` quando ainda não existe token: não há o que invalidar. */
  temTokenAtual: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

/**
 * Confirmação para regenerar o token do Power BI (#143 AC-4). A copy
 * espelha o critério: o token anterior deixa de funcionar imediatamente,
 * e o novo é exibido uma única vez.
 *
 * Sem token ativo a primeira frase seria falsa — prometer a invalidação de
 * algo que não existe faria a confirmação parecer mais grave do que é —,
 * então a emissão do primeiro token tem sua própria copy.
 */
export function ConfirmarRegeneracaoDialog({
  open,
  temTokenAtual,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <SlideOver
      open={open}
      onClose={onCancel}
      title={
        temTokenAtual
          ? "Regenerar token do Power BI"
          : "Gerar token do Power BI"
      }
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            data-testid="powerbi-regenerar-confirmar"
          >
            {temTokenAtual ? "Confirmar regeneração" : "Gerar token"}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 px-4 py-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning-bg text-warning-text">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div className="min-w-0 text-sm leading-relaxed text-text-muted">
            <p className="font-medium text-text">
              {temTokenAtual
                ? "Ao confirmar, o token atual será invalidado imediatamente."
                : "Ao confirmar, o primeiro token de serviço será emitido."}
            </p>
            <p className="mt-1">
              {temTokenAtual
                ? "Qualquer consulta em andamento do Power BI vai falhar até que o novo token seja configurado no conector. "
                : "Ele precisa ser configurado no conector do Power BI para que a exportação passe a responder. "}
              O token é exibido apenas uma vez — anote-o antes de fechar o
              diálogo.
            </p>
          </div>
        </div>
      </div>
    </SlideOver>
  );
}
