import { apiClient } from "@/app/lib/api";

// ─── Constantes espelhadas do backend ────────────────────────────────────────

/** Espelha apps/sgp/constants.py::PARENTESCO_CHOICES. Chave → rótulo. */
export const PARENTESCO_OPTIONS: { value: string; label: string }[] = [
  { value: "titular", label: "Titular" },
  { value: "conjuge", label: "Cônjuge" },
  { value: "filho", label: "Filho(a)" },
  { value: "enteado", label: "Enteado(a)" },
  { value: "pai", label: "Pai" },
  { value: "mae", label: "Mãe" },
  { value: "irmao", label: "Irmão(ã)" },
  { value: "avo", label: "Avô(ó)" },
  { value: "neto", label: "Neto(a)" },
  { value: "outro", label: "Outro" },
];

/**
 * Espelha apps/sgp/constants.py::SAUDE_CHOICES. Valor cru + rótulo humano.
 * `nenhuma` é mutuamente exclusiva com as demais (validate_saude no backend).
 */
export const SAUDE_OPTIONS: { value: string; label: string }[] = [
  { value: "nenhuma", label: "Nenhuma" },
  { value: "diabetes", label: "Diabetes" },
  { value: "hipertensao", label: "Hipertensão" },
  { value: "deficiencia_visual", label: "Deficiência visual" },
  { value: "deficiencia_auditiva", label: "Deficiência auditiva" },
  { value: "deficiencia_motora", label: "Deficiência motora" },
  { value: "deficiencia_intelectual", label: "Deficiência intelectual" },
  { value: "deficiencia_multipla", label: "Deficiência múltipla" },
  { value: "doenca_cardiaca", label: "Doença cardíaca" },
  { value: "doenca_respiratoria", label: "Doença respiratória" },
  { value: "doenca_renal", label: "Doença renal" },
  { value: "saude_mental", label: "Saúde mental" },
  { value: "gestante", label: "Gestante" },
  { value: "lactante", label: "Lactante" },
  { value: "desnutricao", label: "Desnutrição" },
  { value: "alergia_alimentar", label: "Alergia alimentar" },
  { value: "doenca_cronica", label: "Doença crônica" },
  { value: "outros", label: "Outros" },
];

/** Retorna o rótulo humano de um valor de saúde (ou o próprio valor se desconhecido). */
export function saudeLabel(value: string): string {
  return SAUDE_OPTIONS.find((s) => s.value === value)?.label ?? value;
}

/**
 * Escolaridades que indicam vínculo escolar ativo, sobre
 * apps/sgp/constants.py::ESCOLARIDADE_CHOICES: 2 (Fundamental incompleto),
 * 3 (Fundamental completo) e 4 (Médio incompleto). Fora desse conjunto a
 * pessoa não está matriculada, e perguntar a escola só gera ruído.
 */
export const ESCOLARIDADE_COM_VINCULO_ESCOLAR: number[] = [2, 3, 4];

/** A escolaridade informada indica matrícula ativa? */
export function temVinculoEscolar(
  escolaridade: number | null | undefined,
): boolean {
  if (escolaridade === null || escolaridade === undefined) return false;
  return ESCOLARIDADE_COM_VINCULO_ESCOLAR.includes(escolaridade);
}

// ─── Tipos ───────────────────────────────────────────────────────────────────

/**
 * Espelha apps/sgp/serializers.py::MembroListSerializer.
 * genero/cor_raca são choices inteiros; use os `*_display` para exibição.
 *
 * `cor_raca`/`cor_raca_display` são omitidos pelo backend (BE-25/#187) quando o
 * perfil do usuário não tem permissão de leitura — a ausência da chave é o
 * sinal usado pelo frontend para não renderizar o campo (#192).
 */
export type MembroListItem = {
  id: number;
  nome_completo: string;
  data_nascimento: string | null;
  idade: number | null;
  grau_parentesco: string;
  grau_parentesco_display: string;
  cpf: string;
  genero: number | null;
  genero_display: string;
  cor_raca?: number | null;
  cor_raca_display?: string;
  criado_em: string;
};

/**
 * Espelha apps/sgp/serializers.py::MembroDetailSerializer.
 *
 * `cor_raca`/`cor_raca_display` e `saude` são omitidos pelo backend (BE-25/#187)
 * quando o perfil do usuário não tem permissão de leitura — a ausência da chave
 * é o sinal usado pelo frontend para não renderizar o campo (#192).
 */
export type MembroDetail = {
  id: number;
  upf: number;
  nome_completo: string;
  data_nascimento: string | null;
  idade: number | null;
  cpf: string;
  rg: string;
  nis: string;
  caf: string;
  grau_parentesco: string;
  grau_parentesco_display: string;
  genero: number | null;
  genero_display: string;
  cor_raca?: number | null;
  cor_raca_display?: string;
  escola: string;
  seguridade_social: string[];
  saude?: string[];
  escolaridade: number | null;
  escolaridade_display: string;
  criado_por: number | null;
  criado_em: string;
  atualizado_em: string;
};

/** Campos graváveis (POST/PATCH). Campos opcionais podem ser omitidos. */
export type MembroWritePayload = {
  nome_completo: string;
  grau_parentesco: string;
  data_nascimento?: string | null;
  cpf?: string;
  rg?: string;
  nis?: string;
  caf?: string;
  genero?: number | null;
  cor_raca?: number | null;
  escola?: string;
  escolaridade?: number | null;
  saude?: string[];
  seguridade_social?: string[];
};

/**
 * Espelha a resposta de GET /api/v1/sgp/upfs/{upfId}/membros/resumo/ (BE-23).
 * As chaves de `faixa_etaria` são as do backend — use `FAIXAS_ETARIAS` para
 * exibi-las na ordem e com os rótulos certos.
 */
export type ResumoMembros = {
  total_membros: number;
  faixa_etaria: Record<FaixaEtariaKey, number>;
  genero: {
    masculino: number;
    feminino: number;
    nao_binario: number;
    nao_informado: number;
  };
  tem_titular: boolean;
};

export type FaixaEtariaKey =
  | "0-11"
  | "12-17"
  | "18-59"
  | "60+"
  | "sem_data_nascimento";

/**
 * Ordem e rótulos das faixas etárias do card-resumo. A última não é uma faixa
 * de idade: o backend joga ali quem está sem `data_nascimento`, e a soma das
 * cinco fecha com `total_membros`.
 */
export const FAIXAS_ETARIAS: { key: FaixaEtariaKey; label: string }[] = [
  { key: "0-11", label: "0 a 11 anos" },
  { key: "12-17", label: "12 a 17 anos" },
  { key: "18-59", label: "18 a 59 anos" },
  { key: "60+", label: "60 anos ou mais" },
  { key: "sem_data_nascimento", label: "Sem data de nascimento" },
];

// ─── API ─────────────────────────────────────────────────────────────────────

type Envelope<T> = { count?: number; results?: T[] };

/**
 * GET /api/v1/sgp/upfs/{upfId}/membros/ — lista todos os membros da UPF.
 * Aceita resposta paginada (envelope) ou array cru — retorna sempre um array.
 */
export async function listMembros(
  upfId: string | number,
  signal?: AbortSignal,
): Promise<MembroListItem[]> {
  const res = await apiClient(`/api/v1/sgp/upfs/${upfId}/membros/?limit=1000`, {
    signal,
  });
  const data = (await res.json()) as MembroListItem[] | Envelope<MembroListItem>;
  return Array.isArray(data) ? data : (data.results ?? []);
}

/** GET /api/v1/sgp/upfs/{upfId}/membros/{id}/ — detalhe completo do membro. */
export async function getMembro(
  upfId: string | number,
  id: string | number,
  signal?: AbortSignal,
): Promise<MembroDetail> {
  const res = await apiClient(`/api/v1/sgp/upfs/${upfId}/membros/${id}/`, {
    signal,
  });
  return res.json();
}

/** POST /api/v1/sgp/upfs/{upfId}/membros/ — cria um membro. */
export async function createMembro(
  upfId: string | number,
  payload: MembroWritePayload,
): Promise<MembroDetail> {
  const res = await apiClient(`/api/v1/sgp/upfs/${upfId}/membros/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /api/v1/sgp/upfs/{upfId}/membros/{id}/ — atualiza um membro. */
export async function updateMembro(
  upfId: string | number,
  id: string | number,
  payload: MembroWritePayload,
): Promise<MembroDetail> {
  const res = await apiClient(`/api/v1/sgp/upfs/${upfId}/membros/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** DELETE /api/v1/sgp/upfs/{upfId}/membros/{id}/ — remove um membro. */
export async function deleteMembro(
  upfId: string | number,
  id: string | number,
): Promise<void> {
  await apiClient(`/api/v1/sgp/upfs/${upfId}/membros/${id}/`, {
    method: "DELETE",
  });
}

/**
 * GET /api/v1/sgp/upfs/{upfId}/membros/resumo/ — indicadores agregados da
 * composição familiar (BE-23). É a fonte de `tem_titular` na aba: a listagem
 * local pode estar desatualizada, o resumo vem direto do banco.
 */
export async function getResumoMembros(
  upfId: string | number,
  signal?: AbortSignal,
): Promise<ResumoMembros> {
  const res = await apiClient(`/api/v1/sgp/upfs/${upfId}/membros/resumo/`, {
    signal,
  });
  return res.json();
}

// ─── Helpers de UI ───────────────────────────────────────────────────────────

/**
 * Calcula idade em anos completos a partir de uma data ISO (YYYY-MM-DD).
 * Retorna null quando a data é vazia/inválida. Espelha o backend
 * (MembroListSerializer.get_idade).
 */
export function calcIdade(dataNasc: string | null | undefined): number | null {
  if (!dataNasc) return null;
  const parts = dataNasc.split("-");
  if (parts.length !== 3) return null;
  const [y, m, d] = parts.map(Number);
  if (!y || !m || !d) return null;

  const nasc = new Date(y, m - 1, d);
  if (Number.isNaN(nasc.getTime())) return null;

  const hoje = new Date();
  let anos = hoje.getFullYear() - nasc.getFullYear();
  const passouAniv =
    hoje.getMonth() > nasc.getMonth() ||
    (hoje.getMonth() === nasc.getMonth() && hoje.getDate() >= nasc.getDate());
  if (!passouAniv) anos -= 1;
  return anos >= 0 ? anos : null;
}
