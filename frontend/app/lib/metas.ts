import { apiClient } from "@/app/lib/api";
import type { Acao } from "@/app/lib/acoes";
import type { Paginated } from "@/app/lib/users";
import type { BadgeStatus } from "@/app/components/ui/Badge/Badge";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Constantes ─────────────────────────────────────────────────────────────

/**
 * Objetivos de Desenvolvimento Sustentável — espelha
 * apps/sgp/constants.py::ODS_CHOICES.
 *
 * Lista fechada de 1–17 definida pela ONU: não muda e não justifica um
 * round-trip ao endpoint /choices/ (que hoje nem a expõe).
 */
export const ODS_OPTIONS: ReadonlyArray<{ id: number; label: string }> = [
  { id: 1, label: "ODS 1 – Erradicação da Pobreza" },
  { id: 2, label: "ODS 2 – Fome Zero e Agricultura Sustentável" },
  { id: 3, label: "ODS 3 – Saúde e Bem-Estar" },
  { id: 4, label: "ODS 4 – Educação de Qualidade" },
  { id: 5, label: "ODS 5 – Igualdade de Gênero" },
  { id: 6, label: "ODS 6 – Água Potável e Saneamento" },
  { id: 7, label: "ODS 7 – Energia Acessível e Limpa" },
  { id: 8, label: "ODS 8 – Trabalho Decente e Crescimento Econômico" },
  { id: 9, label: "ODS 9 – Indústria, Inovação e Infraestrutura" },
  { id: 10, label: "ODS 10 – Redução das Desigualdades" },
  { id: 11, label: "ODS 11 – Cidades e Comunidades Sustentáveis" },
  { id: 12, label: "ODS 12 – Consumo e Produção Responsáveis" },
  { id: 13, label: "ODS 13 – Ação contra a Mudança Global do Clima" },
  { id: 14, label: "ODS 14 – Vida na Água" },
  { id: 15, label: "ODS 15 – Vida Terrestre" },
  { id: 16, label: "ODS 16 – Paz, Justiça e Instituições Eficazes" },
  { id: 17, label: "ODS 17 – Parcerias e Meios de Implementação" },
];

/** Rótulo curto ("ODS 7") para uso em chips e resumos. */
export function odsShortLabel(id: number): string {
  return `ODS ${id}`;
}

/**
 * Números de Meta aceitos pelo backend (1–7, ver o MinValue/MaxValue de
 * WorkPlanMeta.numero). São as 7 Metas do PDHC III.
 */
export const META_NUMEROS: readonly number[] = [1, 2, 3, 4, 5, 6, 7];

export const META_NUMERO_OPTIONS: SelectOption[] = META_NUMEROS.map((n) => ({
  value: String(n),
  label: `Meta ${n}`,
}));

// ─── Status ─────────────────────────────────────────────────────────────────

/** Valores de WorkPlanMeta.status_calculado. */
export type MetaStatus = "no_prazo" | "em_atraso" | "concluida";

/**
 * Mapeia o status calculado para um status do design system. Reaproveita os
 * tokens semânticos já existentes no Badge em vez de criar variantes novas:
 * no prazo → info, em atraso → erro, concluída → sucesso.
 */
const BADGE_STATUS: Record<MetaStatus, BadgeStatus> = {
  no_prazo: "planejado",
  em_atraso: "atrasada",
  concluida: "concluido",
};

const STATUS_LABEL: Record<MetaStatus, string> = {
  no_prazo: "No prazo",
  em_atraso: "Em atraso",
  concluida: "Concluída",
};

export function badgeStatusForMeta(status: string): BadgeStatus {
  return BADGE_STATUS[status as MetaStatus] ?? "planejado";
}

export function metaStatusLabel(status: string): string {
  return STATUS_LABEL[status as MetaStatus] ?? status;
}

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/sgp/serializers_workplan.py::WorkPlanMetaListSerializer. */
export type MetaListItem = {
  id: number;
  numero: number;
  titulo: string;
  data_inicio: string;
  data_fim: string;
  /** DecimalField → string no DRF; soma de (quantidade × valor unitário) das Ações. */
  valor_total_planejado: string | null;
  status_calculado: MetaStatus;
  criado_por: string | null;
  criado_em: string;
};

/**
 * Ação do Plano de Trabalho aninhada no detalhe da Meta.
 *
 * O WorkPlanMetaDetailSerializer devolve o array completo com os mesmos campos
 * do WorkPlanAcaoSerializer, então o tipo é o mesmo de acoes.ts — manter duas
 * definições só criaria oportunidade de divergirem.
 */
export type MetaAcao = Acao;

/** Espelha WorkPlanMetaDetailSerializer. */
export type MetaDetail = MetaListItem & {
  descricao: string;
  ods_ids: number[];
  atualizado_em: string;
  acoes: Acao[];
};

/** Campos graváveis (os demais são read_only no serializer). */
export type MetaWritePayload = {
  numero: number;
  titulo: string;
  descricao: string;
  ods_ids: number[];
  data_inicio: string;
  data_fim: string;
};

// ─── API ────────────────────────────────────────────────────────────────────

const BASE_PATH = "/api/v1/metas/";

/**
 * GET /api/v1/metas/
 *
 * São no máximo 7 registros (numero é 1–7 e único), então a listagem busca
 * tudo de uma vez e a tela não pagina. `page_size` acompanha o
 * PageNumberPagination do backend (UPFPagination).
 */
export async function listMetas(
  signal?: AbortSignal,
): Promise<MetaListItem[]> {
  const res = await apiClient(`${BASE_PATH}?page_size=100&ordering=numero`, {
    signal,
  });
  const data: Paginated<MetaListItem> = await res.json();
  return data.results;
}

/** GET /api/v1/metas/{id}/ — detalhe (inclui descrição, ODS e ações). */
export async function getMeta(
  id: number,
  signal?: AbortSignal,
): Promise<MetaDetail> {
  const res = await apiClient(`${BASE_PATH}${id}/`, { signal });
  return res.json();
}

/** POST /api/v1/metas/ — restrito a UGP/Super Admin no backend. */
export async function createMeta(
  payload: MetaWritePayload,
): Promise<MetaDetail> {
  const res = await apiClient(BASE_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /api/v1/metas/{id}/ — restrito a UGP/Super Admin no backend. */
export async function updateMeta(
  id: number,
  payload: MetaWritePayload,
): Promise<MetaDetail> {
  const res = await apiClient(`${BASE_PATH}${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/**
 * DELETE /api/v1/metas/{id}/
 *
 * O backend responde 400 com `{detail: "..."}` quando a Meta tem Ações
 * vinculadas; o apiClient converte isso em ApiError com a mensagem pronta
 * para exibição, então o chamador só precisa mostrá-la.
 */
export async function deleteMeta(id: number): Promise<void> {
  await apiClient(`${BASE_PATH}${id}/`, { method: "DELETE" });
}
