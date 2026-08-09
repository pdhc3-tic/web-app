export type ProgressBarTone = "primary" | "warning" | "success";

export type ProgressBarProps = {
  /** 0–100. `null` desenha o trilho vazio (sem denominador para comparar). */
  value: number | null;
  /**
   * Rótulo acessível do que está sendo medido — vira o aria-label da barra.
   * Ex.: "Progresso da Ação 1.3".
   */
  label: string;
  /**
   * Texto que descreve o valor para leitores de tela e substitui a leitura
   * seca do percentual. Ex.: "2 de 12 intercâmbios".
   */
  valueText?: string;
  tone?: ProgressBarTone;
  className?: string;
};

const fillClass: Record<ProgressBarTone, string> = {
  primary: "bg-primary",
  warning: "bg-warning-text",
  success: "bg-success-text",
};

/**
 * Barra de progresso horizontal.
 *
 * O trilho tem cor própria e permanece visível em 0% de propósito: no Plano de
 * Trabalho é comum uma Ação passar boa parte do projeto perto de zero, e uma
 * barra que some nesse estado não comunica "quase nada feito" — comunica
 * "quebrado".
 */
export function ProgressBar({
  value,
  label,
  valueText,
  tone = "primary",
  className,
}: ProgressBarProps) {
  const indeterminado = value === null || Number.isNaN(value);
  const pct = indeterminado ? 0 : Math.min(100, Math.max(0, value));

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      // Sem denominador não há valor a anunciar: omitir aria-valuenow é o que
      // sinaliza "indeterminado" no padrão ARIA.
      aria-valuenow={indeterminado ? undefined : Math.round(pct)}
      aria-valuetext={valueText}
      className={`h-1.5 w-full overflow-hidden rounded-full bg-surface-muted ${
        className ?? ""
      }`}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-300 motion-reduce:transition-none ${fillClass[tone]}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
