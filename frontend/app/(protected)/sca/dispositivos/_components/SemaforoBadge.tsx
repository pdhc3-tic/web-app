import { statusLabel, type StatusConexao } from "@/app/lib/sca";

/**
 * Indicador visual do estado de conexão do dispositivo (RF criterion #156).
 * Cores derivadas dos tokens semânticos do design system (success/warning/error).
 * O rótulo textual acompanha o ponto para não depender só da cor (a11y).
 */
export function SemaforoBadge({ status }: { status: StatusConexao }) {
  const s = TOKENS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-medium ${s.wrapper}`}
      aria-label={`Status: ${statusLabel(status)}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {statusLabel(status)}
    </span>
  );
}

const TOKENS: Record<StatusConexao, { wrapper: string; dot: string }> = {
  verde: {
    wrapper: "border-success-text/40 bg-success-bg text-success-text",
    dot: "bg-success-text",
  },
  laranja: {
    wrapper: "border-warning-text/40 bg-warning-bg text-warning-text",
    dot: "bg-warning-text",
  },
  vermelho: {
    wrapper: "border-error-text/40 bg-error-bg text-error-text",
    dot: "bg-error-text",
  },
  "sem-sync": {
    wrapper: "border-error-text/40 bg-error-bg text-error-text",
    dot: "bg-error-text",
  },
};
