import { nivelLabel, type NivelSemaforo } from "@/app/lib/semaforo";

/**
 * Badge do semáforo de execução das Ações (RF17).
 *
 * Componente próprio, e não uma variante do <Badge>: os status daquele são de
 * DOMÍNIO ("Concluído", "Adiada", "Cancelada") e reusá-los aqui faria a tela
 * dizer que uma Ação está "Concluída" quando ela só está no ritmo. As cores,
 * essas sim, são os mesmos tokens semânticos do design system — Sucesso,
 * Atenção e Erro — sem nenhum valor literal.
 *
 * A cor nunca é o único portador do significado: cada nível tem forma de ícone
 * própria e rótulo em texto, para quem não distingue verde de vermelho.
 */

export type SemaforoBadgeProps = {
  nivel: NivelSemaforo;
  /** Sobrescreve o rótulo padrão do nível. */
  label?: string;
  /** Some com o texto e mantém só o ponto — para uso em espaço apertado. */
  compact?: boolean;
  className?: string;
};

/**
 * Mapeamento nível → paleta semântica. É este objeto que o teste de componente
 * verifica contra as variáveis CSS do design system.
 */
const nivelClass: Record<NivelSemaforo, string> = {
  verde: "bg-success-bg text-success-text border-success-text",
  amarelo: "bg-warning-bg text-warning-text border-warning-text",
  vermelho: "bg-error-bg text-error-text border-error-text",
  // Ausência de dado não é um estado do semáforo: neutro, sem alarme falso.
  "sem-dado": "bg-neutral-bg text-neutral-text border-neutral-text border-dashed",
};

/** Formas distintas por nível — o que sustenta a leitura sem cor. */
function NivelIcon({ nivel }: { nivel: NivelSemaforo }) {
  const common = {
    className: "w-3 h-3 shrink-0",
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (nivel) {
    case "verde":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M5.5 8.2l1.8 1.8 3.2-3.6" />
        </svg>
      );
    case "amarelo":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M8 5v3.5" />
          <circle cx="8" cy="11" r="0.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "vermelho":
      return (
        <svg {...common}>
          <path d="M8 2.5l5.5 10h-11z" />
          <path d="M8 6.5v3" />
          <circle cx="8" cy="11.4" r="0.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "sem-dado":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" strokeDasharray="2 2" />
          <path d="M5.5 8h5" />
        </svg>
      );
  }
}

export function SemaforoBadge({
  nivel,
  label,
  compact = false,
  className,
}: SemaforoBadgeProps) {
  const texto = label ?? nivelLabel(nivel);

  return (
    <span
      data-testid="semaforo-badge"
      data-nivel={nivel}
      title={compact ? texto : undefined}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-medium leading-[1.4] whitespace-nowrap ${nivelClass[nivel]} ${className ?? ""}`}
    >
      <NivelIcon nivel={nivel} />
      <span className={compact ? "sr-only" : undefined}>{texto}</span>
    </span>
  );
}
