"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { deleteProducaoMock } from "./producaoMock";

type Props = {
  open: boolean;
  onClose: () => void;
  upfId: string;
  producaoId: number | null;
  descricao: string;
  onDeleted: (id: number) => void;
};

export function RemoverProducaoDialog({ open, onClose, upfId, producaoId, descricao, onDeleted }: Props) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (deleting || producaoId == null) return;
    setError(null);
    setDeleting(true);
    try {
      await deleteProducaoMock(upfId, producaoId);
      onDeleted(producaoId);
    } catch {
      setError("Não foi possível remover. Tente novamente.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={deleting ? () => {} : onClose}
      title="Remover atividade produtiva"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={deleting}>Cancelar</Button>
          <Button variant="danger" onClick={handleConfirm} loading={deleting}>Confirmar</Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 px-4 py-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text">
              Remover <span className="font-semibold">{descricao}</span>?
            </p>
            <p className="mt-1 text-sm leading-relaxed text-text-muted">
              Esta ação não poderá ser desfeita.
            </p>
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text">
            {error}
          </div>
        )}
      </div>
    </SlideOver>
  );
}
