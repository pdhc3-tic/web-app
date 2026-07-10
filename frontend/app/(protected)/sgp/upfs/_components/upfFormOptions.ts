import type { SelectOption } from "@/app/components/ui/Select/Select";

// Listas curadas no frontend. O backend armazena strings livres (sem choices),
// então value === label. Convenções usuais (IBGE etc.).

function opts(...labels: string[]): SelectOption[] {
  return labels.map((l) => ({ value: l, label: l }));
}

export const GENERO_OPTIONS = opts(
  "Masculino",
  "Feminino",
  "Outro",
  "Prefere não informar",
);

export const COR_RACA_OPTIONS = opts(
  "Branca",
  "Preta",
  "Parda",
  "Amarela",
  "Indígena",
);

export const ESTADO_CIVIL_OPTIONS = opts(
  "Solteiro(a)",
  "Casado(a)",
  "União estável",
  "Divorciado(a)",
  "Separado(a)",
  "Viúvo(a)",
);

export const ESCOLARIDADE_OPTIONS = opts(
  "Sem escolaridade",
  "Fundamental incompleto",
  "Fundamental completo",
  "Médio incompleto",
  "Médio completo",
  "Superior incompleto",
  "Superior completo",
  "Pós-graduação",
);

export const PCT_OPTIONS = opts(
  "Não se aplica",
  "Quilombola",
  "Indígena",
  "Ribeirinho",
  "Extrativista",
  "Pescador artesanal",
  "Assentado",
  "Outro",
);

export const POSSE_TERRA_OPTIONS = opts(
  "Proprietário",
  "Posseiro",
  "Arrendatário",
  "Parceiro",
  "Comodatário",
  "Assentado",
  "Sem terra",
);

export const TIPO_MORADIA_OPTIONS = opts(
  "Própria",
  "Alugada",
  "Cedida",
  "Financiada",
  "Ocupação",
);

export const SITUACAO_MORADIA_OPTIONS = opts(
  "Regular",
  "Irregular",
  "Em regularização",
);

export const ENERGIA_OPTIONS = opts(
  "Rede pública",
  "Solar",
  "Gerador",
  "Não possui",
);

export const AGUA_OPTIONS = opts(
  "Rede pública",
  "Poço",
  "Nascente",
  "Cisterna",
  "Caminhão-pipa",
  "Rio/açude",
);

export const DISPOSITIVO_OPTIONS = opts(
  "Smartphone",
  "Tablet",
  "Computador",
  "Nenhum",
);

export const SEGURIDADE_OPTIONS = opts(
  "Aposentadoria",
  "BPC/LOAS",
  "Bolsa Família",
  "Auxílio Brasil",
  "Pensão",
  "Seguro-defeso",
  "Nenhum",
  "Outros",
);

/**
 * Garante que o valor atual apareça no select mesmo que não esteja na lista
 * curada (ex.: dado legado de texto livre gravado antes desta tela).
 */
export function withCurrentValue(
  options: SelectOption[],
  value: string | null | undefined,
): SelectOption[] {
  if (!value) return options;
  if (options.some((o) => o.value === value)) return options;
  return [{ value, label: value }, ...options];
}
