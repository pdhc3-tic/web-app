import { PRECEDENCIA_LABEL, precedenciaDo, type LimiteGasto } from "@/app/lib/limites";

const COR: Record<ReturnType<typeof precedenciaDo>, string> = {
  padrao: "border-border bg-surface-muted text-text-muted",
  herdado: "border-info-text/40 bg-info-bg text-info-text",
  sobrescrito: "border-warning-text/40 bg-warning-bg text-warning-text",
};

const TITULO: Record<ReturnType<typeof precedenciaDo>, string> = {
  padrao: "Valor que cada pessoa do perfil recebe nesta rubrica.",
  herdado: "A linha nasceu do padrão do perfil na primeira reserva do período.",
  sobrescrito: "Valor definido pela UGP para esta pessoa, com justificativa; vale sobre o padrão do perfil.",
};

/**
 * De onde vem o valor do limite (#400): o padrão do perfil, a linha herdada
 * dele, ou uma sobrescrita individual. Lê o `escopo`/`herdado` que o backend
 * gravou — não recalcula a precedência.
 */
export function PrecedenciaSelo({ limite }: { limite: Pick<LimiteGasto, "escopo" | "herdado"> }) {
  const p = precedenciaDo(limite);
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-2xs font-medium ${COR[p]}`}
      title={TITULO[p]}
      data-testid="limite-precedencia"
      data-precedencia={p}
    >
      {PRECEDENCIA_LABEL[p]}
    </span>
  );
}
