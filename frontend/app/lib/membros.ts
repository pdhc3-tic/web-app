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

/** Espelha apps/sgp/constants.py::SAUDE_CHOICES. Valor cru + rótulo humano. */
export const SAUDE_OPTIONS: { value: string; label: string }[] = [
  { value: "diabetes", label: "Diabetes" },
  { value: "hipertensao", label: "Hipertensão" },
  { value: "deficiencia_visual", label: "Deficiência visual" },
  { value: "deficiencia_auditiva", label: "Deficiência auditiva" },
  { value: "deficiencia_fisica", label: "Deficiência física" },
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

// ─── Tipos ───────────────────────────────────────────────────────────────────

/**
 * Espelha apps/sgp/serializers.py::MembroListSerializer.
 * genero/cor_raca são choices inteiros; use os `*_display` para exibição.
 */
export type MembroListItem = {
  id: number;
  nome: string;
  data_nasc: string | null;
  idade: number | null;
  parentesco: string;
  parentesco_display: string;
  cpf: string;
  genero: number | null;
  genero_display: string;
  cor_raca: number | null;
  cor_raca_display: string;
  criado_em: string;
};

/** Espelha apps/sgp/serializers.py::MembroDetailSerializer. */
export type MembroDetail = {
  id: number;
  upf: number;
  nome: string;
  data_nasc: string | null;
  idade: number | null;
  cpf: string;
  rg: string;
  nis: string;
  caf: string;
  parentesco: string;
  parentesco_display: string;
  genero: number | null;
  genero_display: string;
  cor_raca: number | null;
  cor_raca_display: string;
  escola: string;
  seguridade_social: string[];
  saude: string[];
  escolaridade: number | null;
  escolaridade_display: string;
  criado_por: number | null;
  criado_em: string;
  atualizado_em: string;
};

/** Campos graváveis (POST/PATCH). Campos opcionais podem ser omitidos. */
export type MembroWritePayload = {
  nome: string;
  parentesco: string;
  data_nasc?: string | null;
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

// ─── API ─────────────────────────────────────────────────────────────────────

type Envelope<T> = { count?: number; results?: T[] };

/**
 * GET /api/v1/upfs/{upfId}/membros/ — lista todos os membros da UPF.
 * Aceita resposta paginada (envelope) ou array cru — retorna sempre um array.
 */
export async function listMembros(
  upfId: string | number,
  signal?: AbortSignal,
): Promise<MembroListItem[]> {
  const res = await apiClient(`/api/v1/upfs/${upfId}/membros/?limit=1000`, {
    signal,
  });
  const data = (await res.json()) as MembroListItem[] | Envelope<MembroListItem>;
  return Array.isArray(data) ? data : (data.results ?? []);
}

/** GET /api/v1/upfs/{upfId}/membros/{id}/ — detalhe completo do membro. */
export async function getMembro(
  upfId: string | number,
  id: string | number,
  signal?: AbortSignal,
): Promise<MembroDetail> {
  const res = await apiClient(`/api/v1/upfs/${upfId}/membros/${id}/`, {
    signal,
  });
  return res.json();
}

/** POST /api/v1/upfs/{upfId}/membros/ — cria um membro. */
export async function createMembro(
  upfId: string | number,
  payload: MembroWritePayload,
): Promise<MembroDetail> {
  const res = await apiClient(`/api/v1/upfs/${upfId}/membros/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /api/v1/upfs/{upfId}/membros/{id}/ — atualiza um membro. */
export async function updateMembro(
  upfId: string | number,
  id: string | number,
  payload: MembroWritePayload,
): Promise<MembroDetail> {
  const res = await apiClient(`/api/v1/upfs/${upfId}/membros/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** DELETE /api/v1/upfs/{upfId}/membros/{id}/ — remove um membro. */
export async function deleteMembro(
  upfId: string | number,
  id: string | number,
): Promise<void> {
  await apiClient(`/api/v1/upfs/${upfId}/membros/${id}/`, {
    method: "DELETE",
  });
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
