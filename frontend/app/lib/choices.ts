import { apiClient } from "@/app/lib/api";
import type { SelectOption } from "@/app/components/ui/Select/Select";

/**
 * Choices do SGP — fonte única: `GET /api/v1/choices/` (`SGPChoicesView`,
 * `CHOICES_PUBLICADOS` em `apps/sgp/views/choices.py`), coberto no backend por
 * teste de contrato (#272).
 *
 * O frontend NÃO mantém cópia das listas: declara só as chaves que consome.
 * Se a resposta vier sem alguma delas, ou malformada, a carga falha com um erro
 * explícito — uma lista silenciosamente defasada aceitaria uma opção que o
 * backend recusa, ou esconderia uma que ele aceita.
 */
export const CHAVES_CHOICES = [
  // UPF e membros (value inteiro no backend, string aqui)
  "genero",
  "cor_raca",
  "escolaridade",
  "dispositivo",
  "pct",
  "posse_terra",
  "situacao_moradia",
  "tipo_moradia",
  "material_construcao",
  "energia",
  "agua",
  "grau_parentesco",
  "saude",
  "seguridade_social",
  // Plano de Trabalho
  "ods",
  "status_plano_trabalho",
  // Atividade
  "tipo_atividade",
  "forma_atuacao",
  "ambito",
  "status_atividade",
  // Produção
  "producao_tipo",
  "producao_sistema_criacao",
  "producao_tipo_outra",
  // Documentos
  "upf_documento_tipo",
  "atividade_documento_tipo",
] as const;

export type ChaveChoice = (typeof CHAVES_CHOICES)[number];

/** Cada chave → opções prontas para o `<Select>` (value sempre string). */
export type SgpChoices = Record<ChaveChoice, SelectOption[]>;

/** Choices vazios: o que os selects mostram enquanto a carga não terminou. */
export const CHOICES_VAZIOS = Object.fromEntries(
  CHAVES_CHOICES.map((chave) => [chave, []]),
) as unknown as SgpChoices;

/** A resposta não cumpre o contrato do endpoint. */
export class ChoicesInvalidosError extends Error {
  constructor(detalhe: string) {
    super(`As opções dos formulários vieram incompletas da API (${detalhe}).`);
    this.name = "ChoicesInvalidosError";
  }
}

type RawChoice = { value: string | number; label: string };

function normalizar(chave: ChaveChoice, raw: unknown): SelectOption[] {
  if (!Array.isArray(raw) || raw.length === 0) {
    throw new ChoicesInvalidosError(`lista "${chave}" ausente ou vazia`);
  }
  return (raw as RawChoice[]).map((item) => {
    if (
      !item ||
      typeof item !== "object" ||
      item.value === undefined ||
      item.value === null ||
      typeof item.label !== "string"
    ) {
      throw new ChoicesInvalidosError(`item malformado em "${chave}"`);
    }
    // O <Select> opera com string; os choices da UPF vêm como int.
    return { value: String(item.value), label: item.label };
  });
}

/**
 * GET /api/v1/choices/ — todas as listas de uma vez. Lança `ApiError` (rede,
 * 4xx/5xx) ou `ChoicesInvalidosError` (contrato quebrado); quem consome mostra
 * o erro em vez de selects vazios sem explicação.
 */
export async function fetchSgpChoices(signal?: AbortSignal): Promise<SgpChoices> {
  const res = await apiClient("/api/v1/choices/", { signal });
  const data = (await res.json()) as Record<string, unknown>;
  if (!data || typeof data !== "object") {
    throw new ChoicesInvalidosError("resposta não é um objeto");
  }
  return Object.fromEntries(
    CHAVES_CHOICES.map((chave) => [chave, normalizar(chave, data[chave])]),
  ) as SgpChoices;
}

/** Rótulo de um valor numa lista de choices; o próprio valor se não achar. */
export function rotuloDe(opcoes: SelectOption[], valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "";
  return opcoes.find((o) => o.value === String(valor))?.label ?? String(valor);
}
