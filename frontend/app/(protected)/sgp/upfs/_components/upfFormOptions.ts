import type { SelectOption } from "@/app/components/ui/Select/Select";

/**
 * As listas de choice moram em @/app/lib/choices.ts, onde servem de fallback
 * para o GET /api/v1/choices/. Reexportadas aqui por compatibilidade com os
 * imports já existentes do módulo UPF.
 *
 * Em componente, prefira `useSgpChoices()` (SgpChoicesProvider): ele devolve o
 * que o backend serve, caindo nestas listas quando o endpoint não responde.
 * Estas constantes diretas só fazem sentido fora de React.
 */
export {
  GENERO_OPTIONS,
  COR_RACA_OPTIONS,
  ESCOLARIDADE_OPTIONS,
  DISPOSITIVO_OPTIONS,
  PCT_OPTIONS,
  POSSE_TERRA_OPTIONS,
  SITUACAO_MORADIA_OPTIONS,
  TIPO_MORADIA_OPTIONS,
  MATERIAL_CONSTRUCAO_OPTIONS,
  ENERGIA_OPTIONS,
  AGUA_OPTIONS,
  SEGURIDADE_OPTIONS,
} from "@/app/lib/choices";

/**
 * Garante que o valor atual apareça no select mesmo que não esteja na lista
 * (ex.: dado legado gravado antes desta tela).
 */
export function withCurrentValue(
  options: SelectOption[],
  value: string | null | undefined,
): SelectOption[] {
  if (!value) return options;
  if (options.some((o) => o.value === value)) return options;
  return [{ value, label: value }, ...options];
}

/**
 * Rótulo humano de um valor de choice inteiro, para exibição na ficha (o detalhe
 * da UPF retorna o id cru desses campos, sem `*_display`). Retorna "" quando nulo.
 */
export function labelForValue(
  options: SelectOption[],
  value: number | string | null | undefined,
): string {
  if (value === null || value === undefined || value === "") return "";
  const v = String(value);
  return options.find((o) => o.value === v)?.label ?? v;
}
