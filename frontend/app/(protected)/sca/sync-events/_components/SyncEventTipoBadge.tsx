import type { TipoEvento } from "@/app/lib/sca";

const LABELS: Record<TipoEvento, string> = {
  push: "Push",
  pull: "Pull",
  refresh: "Refresh",
};

const CLASSES: Record<TipoEvento, string> = {
  // Push/pull/refresh são estados factuais, não avaliativos — só variam de
  // tonalidade para diferenciar visualmente, sem carregar carga semântica
  // (não usar success/error aqui).
  push: "border-primary/40 bg-primary/10 text-primary",
  pull: "border-text-muted/40 bg-surface-muted text-text-muted",
  refresh: "border-text-muted/40 bg-surface-muted text-text-muted",
};

export function SyncEventTipoBadge({ tipo }: { tipo: TipoEvento }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-medium ${CLASSES[tipo]}`}
    >
      {LABELS[tipo]}
    </span>
  );
}
