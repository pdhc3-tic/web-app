import { apiClient } from "@/app/lib/api";
import type { BadgeStatus } from "@/app/components/ui/Badge/Badge";

/**
 * SGD — Demandas (#294).
 *
 * Tipos escritos à mão: a #294 pede os tipos gerados do schema (#273), mas o
 * schema ainda não descreve o `DemandViewSet` (é um `ViewSet` sem serializer
 * declarado) — ver docs/pendencias-backend-sprint-10.md, itens 5 e 6.
 * Espelham `apps/sgd/serializers/demand.py`.
 */

// ─── Tipos ───────────────────────────────────────────────────────────────────

/** Espelha `apps/sgd/models/demand.py::STATUS_CHOICES`. */
export type StatusDemanda =
  | "rascunho"
  | "submetida"
  | "devolvida"
  | "pre_autorizada"
  | "autorizada"
  | "em_atendimento"
  | "concluida"
  | "recusada"
  | "cancelada";

/**
 * `DemandContextoSerializer`: o contexto herdado da atividade, já resolvido
 * pelo backend. Só Ação e Meta — o SGP não modela Submeta nem Indicador
 * (docs/pendencias-backend-sprint-10.md, item 7).
 */
export type ContextoDemanda = {
  territorio_id: number | null;
  territorio_nome: string | null;
  municipio_id: number;
  municipio_nome: string;
  comunidade_id: number | null;
  comunidade_nome: string | null;
  data_prevista: string;
  tecnico_id: number;
  tecnico_nome: string;
  acao_numero: string;
  acao_descricao: string;
  meta_numero: number;
  meta_titulo: string;
};

/** `DemandSerializer` — leitura. Valores monetários vêm como string decimal. */
export type Demanda = {
  id: number;
  titulo: string;
  activity: number;
  justificativa: string;
  status: StatusDemanda;
  status_display: string;
  transicoes_permitidas: StatusDemanda[];
  solicitante: number;
  despesa_posterior: boolean;
  valor_estimado_total: string;
  valor_autorizado_total: string;
  valor_pago_total: string;
  contexto: ContextoDemanda;
  criado_em: string;
  atualizado_em: string;
};

/** Os cinco campos mínimos da atividade criada junto com a demanda. */
export type AtividadeInline = {
  titulo: string;
  tipo_atividade: string;
  acao_id: number;
  municipio_id: number;
  /** YYYY-MM-DD. */
  data_prevista: string;
};

/**
 * `DemandCreateSerializer`: OU `activity_id`, OU os cinco `activity_*` — o
 * backend cria a atividade em Planejado e a demanda na mesma transação.
 */
export type NovaDemandaPayload = {
  titulo: string;
  justificativa: string;
} & ({ atividadeId: number } | { atividade: AtividadeInline });

// ─── Status ──────────────────────────────────────────────────────────────────

/**
 * Cor de cada status no `Badge`. Rascunho e devolvida pedem ação de quem
 * solicitou; as três finais separam o desfecho bom do encerrado.
 */
const BADGE_POR_STATUS: Record<StatusDemanda, BadgeStatus> = {
  rascunho: "planejado",
  submetida: "agendado",
  devolvida: "adiada",
  pre_autorizada: "sem-evidencia",
  autorizada: "em-andamento",
  em_atendimento: "em-andamento",
  concluida: "concluido",
  recusada: "nao-realizada",
  cancelada: "cancelada",
};

export function badgeStatusDaDemanda(status: StatusDemanda): BadgeStatus {
  return BADGE_POR_STATUS[status] ?? "planejado";
}

/**
 * Espelha `apps/sgd/services/demand.py`. Só orienta a tela — quem recusa é o
 * backend (`criar_demanda`).
 */
export const STATUS_ATIVIDADE_BLOQUEIAM_DEMANDA = ["cancelada", "nao_realizada"];
export const STATUS_ATIVIDADE_EXIGEM_JUSTIFICATIVA = [
  "em_andamento",
  "concluido",
  "concluido_sem_evidencia",
];

/** Status em que uma atividade pode ser escolhida no campo "Atividade" (RF01). */
export const STATUS_ATIVIDADE_ELEGIVEIS = ["planejado", "agendado"];

// ─── API ─────────────────────────────────────────────────────────────────────

const DEMANDAS_PATH = "/api/v1/sgd/demandas/";

/**
 * GET /api/v1/sgd/demandas/?activity={id} — as demandas de uma atividade.
 *
 * O filtro `activity` ainda não existe no `DemandViewSet.list` (só `status`):
 * enquanto isso o backend devolve TODAS as demandas visíveis ao usuário, e a
 * aba mostra o que vier. A lista não é filtrada aqui de propósito — ver
 * docs/pendencias-backend-sprint-10.md, item 6.
 */
export async function listDemandasDaAtividade(
  atividadeId: number | string,
  signal?: AbortSignal,
): Promise<Demanda[]> {
  const qs = new URLSearchParams({ activity: String(atividadeId) });
  const res = await apiClient(`${DEMANDAS_PATH}?${qs}`, { signal });
  return res.json();
}

/** POST /api/v1/sgd/demandas/ — cria a demanda (e a atividade, se for o caso). */
export async function criarDemanda(payload: NovaDemandaPayload): Promise<Demanda> {
  const body: Record<string, unknown> = {
    titulo: payload.titulo,
    justificativa: payload.justificativa,
  };
  if ("atividadeId" in payload) {
    body.activity_id = payload.atividadeId;
  } else {
    const a = payload.atividade;
    body.activity_titulo = a.titulo;
    body.activity_tipo_atividade = a.tipo_atividade;
    body.activity_acao_id = a.acao_id;
    body.activity_municipio_id = a.municipio_id;
    body.activity_data_prevista = a.data_prevista;
  }

  const res = await apiClient(DEMANDAS_PATH, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.json();
}

/** Item da busca do campo "Atividade" — subset de `ActivityListSerializer`. */
export type AtividadeElegivel = {
  id: number;
  titulo: string;
  status: string;
  status_display: string;
  data_inicio: string;
  municipio: { id: number; nome: string };
};

/**
 * GET /api/v1/sgp/atividades/?tecnico_id={eu}&status=planejado&status=agendado&q={texto}
 * — atividades do solicitante que aceitam demanda, para o campo com busca.
 *
 * O contrato é o certo, mas dois filtros ainda não existem no `ActivityFilter`
 * (docs/pendencias-backend-sprint-10.md, item 9): `q` é ignorado — a lista
 * não estreita pelo texto digitado — e `status` só considera o último valor,
 * então hoje vêm só as Agendadas. Nada é filtrado aqui para compensar.
 */
export async function buscarAtividadesElegiveis(
  params: { tecnicoId: string; busca: string },
  signal?: AbortSignal,
): Promise<AtividadeElegivel[]> {
  const qs = new URLSearchParams();
  qs.set("tecnico_id", params.tecnicoId);
  for (const s of STATUS_ATIVIDADE_ELEGIVEIS) qs.append("status", s);
  if (params.busca.trim()) qs.set("q", params.busca.trim());
  qs.set("ordering", "data_inicio");
  qs.set("page_size", "20");

  const res = await apiClient(`/api/v1/sgp/atividades/?${qs}`, { signal });
  const data: { results: AtividadeElegivel[] } = await res.json();
  return data.results;
}
