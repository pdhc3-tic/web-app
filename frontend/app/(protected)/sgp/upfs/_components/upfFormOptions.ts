import type { SelectOption } from "@/app/components/ui/Select/Select";

/**
 * SEGURIDADE_OPTIONS não é publicado pelo endpoint /api/v1/choices/, por isso
 * permanece como constante estática. Para todas as demais listas, use
 * `useSgpChoices()` (SgpChoicesProvider), que devolve o que o backend serve.
 */
export { SEGURIDADE_OPTIONS } from "@/app/lib/choices";

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
