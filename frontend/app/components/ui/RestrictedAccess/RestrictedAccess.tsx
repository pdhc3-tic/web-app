import type { ReactNode } from "react";
import { ShieldX } from "lucide-react";

export type RestrictedAccessProps = {
  /** Código exibido como rótulo superior (padrão "403"). */
  code?: string;
  title?: string;
  description?: ReactNode;
  /** Ícone/ilustração (padrão: escudo). */
  icon?: ReactNode;
};

const DEFAULT_DESCRIPTION =
  "Você não tem permissão para acessar este conteúdo. Se acredita que isto é um engano, entre em contato com um administrador.";

/** Tela genérica de acesso negado (403) com ilustração. */
export function RestrictedAccess({
  code = "403",
  title = "Conteúdo restrito",
  description = DEFAULT_DESCRIPTION,
  icon,
}: RestrictedAccessProps) {
  return (
    <div
      role="alert"
      className="mx-auto flex max-w-xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center"
    >
      <span
        aria-hidden="true"
        className="flex h-16 w-16 items-center justify-center rounded-full bg-error-bg text-error-text"
      >
        {icon ?? <ShieldX className="h-8 w-8" />}
      </span>
      <div className="space-y-1">
        <p className="text-2xs font-medium uppercase tracking-[0.18em] text-error-text">
          Erro {code}
        </p>
        <h2 className="text-lg font-semibold text-text">{title}</h2>
      </div>
      <p className="max-w-md text-sm leading-relaxed text-text-muted">
        {description}
      </p>
    </div>
  );
}
