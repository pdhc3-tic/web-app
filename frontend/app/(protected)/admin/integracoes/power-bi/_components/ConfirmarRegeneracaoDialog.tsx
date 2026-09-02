"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";

type Props = {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

/**
 * Confirmação para regenerar o token do Power BI (#143 AC-4). A copy
 * espelha o critério: o token anterior deixa de funcionar imediatamente,
 * e o novo é exibido uma única vez.
 */
export function ConfirmarRegeneracaoDialog({
  open,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <SlideOver
      open={open}
      onClose={onCancel}
      title="Regenerar token do Power BI"
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
            Confirmar regeneração
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
              Ao confirmar, o token atual será invalidado imediatamente.
            </p>
            <p className="mt-1">
              Qualquer consulta em andamento do Power BI vai falhar até que o
              novo token seja configurado no conector. O novo token é exibido
              apenas uma vez após a regeneração — anote-o antes de fechar o
              diálogo.
            </p>
          </div>
        </div>
      </div>
    </SlideOver>
  );
}
