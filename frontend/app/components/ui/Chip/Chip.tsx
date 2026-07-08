import type { ReactNode } from "react";

export type ChipProps = {
  children: ReactNode;
  /** Tooltip nativo (ex.: lista completa quando o chip resume vários itens). */
  title?: string;
  className?: string;
};

/** Pequeno rótulo arredondado para tags/atributos (perfis, territórios, etc.). */
export function Chip({ children, title, className }: ChipProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-full border border-border bg-surface-muted px-2 py-0.5 text-2xs font-medium text-text whitespace-nowrap ${className ?? ""}`}
    >
      {children}
    </span>
  );
}
