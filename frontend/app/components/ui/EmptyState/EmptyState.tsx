import type { ReactNode } from "react";

export type EmptyStateProps = {
  /** Ícone/ilustração (ex.: um ícone lucide). */
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  /** Ação opcional (ex.: um <Button />). */
  action?: ReactNode;
  className?: string;
};

/** Estado vazio genérico: ícone + título + descrição + ação opcional. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center gap-4 px-6 py-16 text-center ${className ?? ""}`}
    >
      {icon && (
        <span
          aria-hidden="true"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-surface-muted text-text-muted"
        >
          {icon}
        </span>
      )}

      <div className="space-y-1">
        <h2 className="text-base font-semibold text-text">{title}</h2>
        {description && (
          <p className="max-w-sm text-sm leading-relaxed text-text-muted">
            {description}
          </p>
        )}
      </div>

      {action}
    </div>
  );
}
