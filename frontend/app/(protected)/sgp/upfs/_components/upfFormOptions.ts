import type { SelectOption } from "@/app/components/ui/Select/Select";

// Opções espelham apps/sgp/constants.py — o backend armazena estes campos como
// PositiveSmallIntegerField(choices=...). O `value` é o id inteiro (como string,
// pois o <Select> opera com string); o label é o rótulo do backend.

function opt(id: number, label: string): SelectOption {
  return { value: String(id), label };
}

// ── MembroFamilia (titular e demais membros) ──────────────────────────────────

export const GENERO_OPTIONS: SelectOption[] = [
  opt(1, "Masculino"),
  opt(2, "Feminino"),
  opt(3, "Outro"),
  opt(4, "Não Informado"),
];

export const COR_RACA_OPTIONS: SelectOption[] = [
  opt(1, "Branca"),
  opt(2, "Preta"),
  opt(3, "Parda"),
  opt(4, "Amarela"),
  opt(5, "Indígena"),
  opt(6, "Não Informado"),
];

export const ESCOLARIDADE_OPTIONS: SelectOption[] = [
  opt(1, "Sem instrução"),
  opt(2, "Fundamental incompleto"),
  opt(3, "Fundamental completo"),
  opt(4, "Médio incompleto"),
  opt(5, "Médio completo"),
  opt(6, "Superior incompleto"),
  opt(7, "Superior completo"),
  opt(8, "Pós-graduação"),
  opt(9, "Não Informado"),
];

// ── UPF ───────────────────────────────────────────────────────────────────────

export const DISPOSITIVO_OPTIONS: SelectOption[] = [
  opt(1, "Computador"),
  opt(2, "Notebook"),
  opt(3, "Tablet"),
  opt(4, "Smartphone"),
  opt(5, "Não possui"),
  opt(6, "Outro"),
];

export const PCT_OPTIONS: SelectOption[] = [
  opt(1, "Sim"),
  opt(2, "Não"),
  opt(3, "Não Informado"),
];

export const POSSE_TERRA_OPTIONS: SelectOption[] = [
  opt(1, "Própria"),
  opt(2, "Alugada"),
  opt(3, "Cedida"),
  opt(4, "Ocupação"),
  opt(5, "Posse tradicional"),
  opt(6, "Não Informado"),
];

export const SITUACAO_MORADIA_OPTIONS: SelectOption[] = [
  opt(1, "Própria"),
  opt(2, "Alugada"),
  opt(3, "Cedida"),
  opt(4, "Ocupação"),
  opt(5, "Financiada"),
  opt(6, "Não Informado"),
];

export const TIPO_MORADIA_OPTIONS: SelectOption[] = [
  opt(1, "Casa"),
  opt(2, "Apartamento"),
  opt(3, "Cômodo"),
  opt(4, "Barraca"),
  opt(5, "Outro"),
  opt(6, "Não Informado"),
];

export const MATERIAL_CONSTRUCAO_OPTIONS: SelectOption[] = [
  opt(1, "Alvenaria"),
  opt(2, "Madeira"),
  opt(3, "Taipa"),
  opt(4, "Pedra"),
  opt(5, "Misto"),
  opt(6, "Outro"),
  opt(7, "Não Informado"),
];

export const ENERGIA_OPTIONS: SelectOption[] = [
  opt(1, "Sim"),
  opt(2, "Não"),
  opt(3, "Não Informado"),
];

export const AGUA_OPTIONS: SelectOption[] = [
  opt(1, "Rede pública"),
  opt(2, "Poço artesiano"),
  opt(3, "Poço raso"),
  opt(4, "Nascente"),
  opt(5, "Carro-pipa"),
  opt(6, "Chuva"),
  opt(7, "Outro"),
  opt(8, "Não Informado"),
];

// `seguridade_social` continua como JSONField de strings livres no backend
// (UPF e MembroFamilia) — não foi refatorado para choices. Mantém value === label.
export const SEGURIDADE_OPTIONS: SelectOption[] = [
  "Aposentadoria",
  "BPC/LOAS",
  "Bolsa Família",
  "Auxílio Brasil",
  "Pensão",
  "Seguro-defeso",
  "Nenhum",
  "Outros",
].map((l) => ({ value: l, label: l }));

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
