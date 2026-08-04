"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { deleteDocumentoMock } from "./documentoMock";

type Props = {
  open: boolean;
  onClose: () => void;
  upfId: string;
  documentoId: number | null;
  nome: string;
  onDeleted: (id: number) => void;
};

export function RemoverDocumentoDialog({ open, onClose, upfId, documentoId, nome, onDeleted }: Props) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (deleting || documentoId == null) return;
    setError(null);
    setDeleting(true);
    try {
      await deleteDocumentoMock(upfId, documentoId);
      onDeleted(documentoId);
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
      title="Remover documento"
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
              Tem certeza que deseja remover <span className="font-semibold">{nome}</span>?
            </p>
            <p className="mt-1 text-sm leading-relaxed text-text-muted">
              Esta ação não pode ser desfeita.
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
