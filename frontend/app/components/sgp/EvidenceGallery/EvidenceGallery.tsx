"use client";

import { PhotoGallery } from "./PhotoGallery";
import { DocumentList } from "./DocumentList";

export type EvidenceGalleryProps = {
  /** ID (string) da atividade a que as evidências pertencem. */
  atividadeId: string;
  /** Quando true, esconde ações de upload/edição/remoção. */
  readOnly?: boolean;
  className?: string;
};

/**
 * Galeria unificada de evidências (fotos + documentos) de uma atividade do SGP.
 * Concentra as duas coleções no mesmo bloco visual para uso na tela de
 * atividade — cada seção mantém seu próprio fluxo de upload, listagem e edição.
 */
export function EvidenceGallery({
  atividadeId,
  readOnly = false,
  className,
}: EvidenceGalleryProps) {
  return (
    <div className={`flex flex-col gap-6 ${className ?? ""}`}>
      <PhotoGallery atividadeId={atividadeId} readOnly={readOnly} />
      <div className="h-px bg-border" role="separator" aria-hidden="true" />
      <DocumentList atividadeId={atividadeId} readOnly={readOnly} />
    </div>
  );
}

export { PhotoGallery } from "./PhotoGallery";
export { DocumentList } from "./DocumentList";
export * from "./types";
