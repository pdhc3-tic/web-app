import { apiClient } from "@/app/lib/api";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { PARENTESCO_OPTIONS } from "@/app/lib/membros";
import {
  AMBITO_OPTIONS,
  FORMA_ATUACAO_OPTIONS,
  STATUS_OPTIONS,
  TIPO_ATIVIDADE_OPTIONS,
} from "@/app/lib/atividades";

/**
 * Choices do SGP servidos por GET /api/v1/choices/ (SGPChoicesView).
 *
 * As constantes deste arquivo espelham apps/sgp/constants.py e servem de
 * FALLBACK: o endpoint é a fonte da verdade quando responde, e elas entram em
 * cena para chave ausente, malformada ou erro de rede. Assim a UI nunca fica
 * com select vazio, e uma opção nova no backend aparece sem deploy do front.
 *
 * Duas listas do módulo UPF ficam de fora de propósito — ver NAO_MIGRADOS no fim.
 */

function opt(id: number, label: string): SelectOption {
  return { value: String(id), label };
}

// ── MembroFamilia ────────────────────────────────────────────────────────────

export const GENERO_OPTIONS: SelectOption[] = [
  opt(1, "Masculino"),
  opt(2, "Feminino"),
  opt(3, "Não binário"),
  opt(4, "Não informado"),
];

export const COR_RACA_OPTIONS: SelectOption[] = [
  opt(1, "Branca"),
  opt(2, "Preta"),
  opt(3, "Parda"),
  opt(4, "Amarela"),
  opt(5, "Indígena"),
];

export const ESCOLARIDADE_OPTIONS: SelectOption[] = [
  opt(1, "Sem instrução"),
  opt(2, "Fundamental incompleto"),
  opt(3, "Fundamental completo"),
  opt(4, "Médio incompleto"),
  opt(5, "Médio completo"),
  opt(6, "Superior incompleto"),
  opt(7, "Superior completo"),
];

// ── UPF ──────────────────────────────────────────────────────────────────────

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

/**
 * Espelha apps/sgp/constants.py::SEGURIDADE_SOCIAL_CHOICES.
 *
 * O SGPChoicesView não publica esta chave, então a lista fica aqui — mas ela
 * deixou de ser texto livre: MembroDetailSerializer.validate_seguridade_social
 * rejeita valor fora desta lista, e `nenhum` é mutuamente exclusivo com os
 * demais. Enviar o rótulo ("Bolsa Família") em vez da chave agora dá 400.
 */
export const SEGURIDADE_OPTIONS: SelectOption[] = [
  { value: "bpc", label: "BPC/LOAS" },
  { value: "bolsa_familia", label: "Bolsa Família" },
  { value: "aposentadoria", label: "Aposentadoria" },
  { value: "nenhum", label: "Nenhum" },
];

// ── Bundle ───────────────────────────────────────────────────────────────────

/** Chaves de /api/v1/choices/ que o frontend consome. */
export type SgpChoices = {
  // UPF / membro (value inteiro no backend)
  genero: SelectOption[];
  cor_raca: SelectOption[];
  escolaridade: SelectOption[];
  dispositivo: SelectOption[];
  pct: SelectOption[];
  posse_terra: SelectOption[];
  situacao_moradia: SelectOption[];
  tipo_moradia: SelectOption[];
  material_construcao: SelectOption[];
  energia: SelectOption[];
  agua: SelectOption[];
  grau_parentesco: SelectOption[];
  // Atividade (value string) — ainda ausentes no SGPChoicesView
  tipo_atividade: SelectOption[];
  forma_atuacao: SelectOption[];
  ambito: SelectOption[];
  status: SelectOption[];
};

export const FALLBACK_CHOICES: SgpChoices = {
  genero: GENERO_OPTIONS,
  cor_raca: COR_RACA_OPTIONS,
  escolaridade: ESCOLARIDADE_OPTIONS,
  dispositivo: DISPOSITIVO_OPTIONS,
  pct: PCT_OPTIONS,
  posse_terra: POSSE_TERRA_OPTIONS,
  situacao_moradia: SITUACAO_MORADIA_OPTIONS,
  tipo_moradia: TIPO_MORADIA_OPTIONS,
  material_construcao: MATERIAL_CONSTRUCAO_OPTIONS,
  energia: ENERGIA_OPTIONS,
  agua: AGUA_OPTIONS,
  grau_parentesco: PARENTESCO_OPTIONS,
  tipo_atividade: TIPO_ATIVIDADE_OPTIONS,
  forma_atuacao: FORMA_ATUACAO_OPTIONS,
  ambito: AMBITO_OPTIONS,
  status: STATUS_OPTIONS,
};

/** Item do SGPChoicesView. `value` vem int nos choices da UPF e string nos de atividade. */
type RawChoice = { value: string | number; label: string };

/**
 * Aceita a lista do backend só quando ela é um array não-vazio de itens bem
 * formados; qualquer problema descarta a lista INTEIRA e usa o fallback.
 *
 * Descartar tudo em vez de filtrar item a item é deliberado: uma lista
 * silenciosamente incompleta é pior que uma defasada, porque o usuário não tem
 * como perceber que faltou uma opção.
 */
export function normalizeChoiceList(
  raw: unknown,
  fallback: SelectOption[],
): SelectOption[] {
  if (!Array.isArray(raw) || raw.length === 0) return fallback;

  const options: SelectOption[] = [];
  for (const item of raw as RawChoice[]) {
    if (!item || typeof item !== "object") return fallback;
    if (item.value === undefined || item.value === null) return fallback;
    if (typeof item.label !== "string") return fallback;
    // O <Select> opera com string; os choices da UPF vêm como int.
    options.push({ value: String(item.value), label: item.label });
  }
  return options;
}

/**
 * GET /api/v1/choices/ — busca os choices do SGP e normaliza cada chave contra
 * seu fallback local. Nunca lança: erro de rede ou 403 devolve os fallbacks.
 */
export async function fetchSgpChoices(
  signal?: AbortSignal,
): Promise<SgpChoices> {
  let data: Record<string, unknown>;
  try {
    const res = await apiClient("/api/v1/choices/", { signal });
    data = (await res.json()) as Record<string, unknown>;
  } catch {
    return FALLBACK_CHOICES;
  }

  if (!data || typeof data !== "object") return FALLBACK_CHOICES;

  const keys = Object.keys(FALLBACK_CHOICES) as (keyof SgpChoices)[];
  const resolved = {} as SgpChoices;
  for (const key of keys) {
    resolved[key] = normalizeChoiceList(data[key], FALLBACK_CHOICES[key]);
  }
  return resolved;
}

/**
 * Listas que NÃO vêm do endpoint, e por quê:
 *
 * - `seguridade_social` — SEGURIDADE_SOCIAL_CHOICES existe em constants.py e é
 *   validado no serializer, mas o SGPChoicesView não expõe a chave. Use
 *   SEGURIDADE_OPTIONS acima.
 * - `saude` — o SGPChoicesView emite `{"value": v, "label": v}` porque
 *   SAUDE_CHOICES é lista plana de strings, sem rótulo humano. Consumir o
 *   endpoint faria a tela exibir "deficiencia_visual" em vez de "Deficiência
 *   visual". Use SAUDE_OPTIONS de lib/membros.ts até o backend transformar
 *   SAUDE_CHOICES em tuplas (value, label).
 */
