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

/**
 * `DemandRequestSerializer` — uma solicitação de recurso da demanda.
 * `alerta_rubrica_fora_do_previsto`: a rubrica não está entre as previstas da
 * Ação (alerta não bloqueante, RF22).
 */
export type SolicitacaoDemanda = {
  id: number;
  demanda: number;
  tipo: string;
  tipo_display: string;
  rubrica: number;
  rubrica_slug: string;
  rubrica_nome: string;
  campos_json: Record<string, unknown>;
  valor_estimado: string;
  valor_autorizado: string | null;
  valor_pago: string | null;
  ordem: number;
  alerta_rubrica_fora_do_previsto: boolean;
  criado_em: string;
  atualizado_em: string;
};

/**
 * Etapa de aprovação (`ApprovalStep`) — a linha do tempo da demanda.
 *
 * O backend grava as etapas, mas ainda NÃO as expõe
 * (docs/pendencias-backend-sprint-10.md, item 11). O tipo descreve o que o
 * painel espera receber em `Demanda.etapas`.
 */
export type EtapaDemanda = {
  id: number;
  etapa: "pre_autorizacao" | "autorizacao" | "atendimento";
  etapa_display: string;
  acao: "aprovado" | "recusado" | "devolvido" | "atendido";
  acao_display: string;
  responsavel_nome: string | null;
  justificativa: string;
  excedente_autorizado: boolean;
  criado_em: string;
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
  solicitacoes: SolicitacaoDemanda[];
  /**
   * Nome de quem abriu a demanda — ainda NÃO vem (só o id em `solicitante`);
   * docs/pendencias-backend-sprint-10.md, item 12. Opcional até lá.
   */
  solicitante_nome?: string;
  /** Linha do tempo — ainda NÃO vem; ver `EtapaDemanda`. Opcional até lá. */
  etapas?: EtapaDemanda[];
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

// ─── Painel de decisão (#296) ────────────────────────────────────────────────

/** Perfis que decidem sobre demandas (RF18–RF23). */
export type PerfilDecisor = "articulador-estadual" | "ugp" | "fgd";

/**
 * Status que aguardam a decisão de cada perfil — a fila "Aguardando minha
 * ação". Espelha `apps/sgd/services/approval.py` (quem é notificado em cada
 * status) e as permissões de `DemandApprovalMixin`.
 */
export const STATUS_AGUARDANDO: Record<PerfilDecisor, StatusDemanda[]> = {
  "articulador-estadual": ["submetida"],
  ugp: ["pre_autorizada"],
  fgd: ["autorizada", "em_atendimento"],
};

/**
 * GET /api/v1/sgd/demandas/?status=… — listagem, já no escopo do perfil
 * (o Articulador só enxerga as Submetidas do próprio estado).
 *
 * Vários status vão como parâmetro repetido. O `DemandViewSet.list` hoje só lê
 * o último — para a FGD, que aguarda dois status, a fila vem incompleta
 * (docs/pendencias-backend-sprint-10.md, item 13).
 */
export async function listDemandas(
  params: { status?: StatusDemanda[] } = {},
  signal?: AbortSignal,
): Promise<Demanda[]> {
  const qs = new URLSearchParams();
  for (const st of params.status ?? []) qs.append("status", st);
  const query = qs.toString();
  const res = await apiClient(`${DEMANDAS_PATH}${query ? `?${query}` : ""}`, { signal });
  return res.json();
}

/** GET /api/v1/sgd/demandas/{id}/ */
export async function getDemanda(id: number | string, signal?: AbortSignal): Promise<Demanda> {
  const res = await apiClient(`${DEMANDAS_PATH}${id}/`, { signal });
  return res.json();
}

export type FaixaSemaforo = "verde" | "amarelo" | "vermelho";

type ImpactoTrava = {
  semaforo_antes: FaixaSemaforo | null;
  semaforo_apos: FaixaSemaforo | null;
  saldo_apos: number | string | null;
};

/** Resposta de `preview-decisao` (BE-3): o saldo das duas travas depois da decisão. */
export type PreviewDecisao = {
  disponivel: boolean;
  trava_bloqueada: "individual" | "territorial" | null;
  individual: ImpactoTrava;
  territorial: ImpactoTrava;
};

/**
 * GET /api/v1/sgd/demandas/{id}/preview-decisao/?demand_request_id=&valor=
 * `valor` é o valor que a decisão vai reservar para a solicitação.
 */
export async function previewDecisao(
  demandaId: number,
  solicitacaoId: number,
  valor: string,
  signal?: AbortSignal,
): Promise<PreviewDecisao> {
  const qs = new URLSearchParams({ demand_request_id: String(solicitacaoId), valor });
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/preview-decisao/?${qs}`, { signal });
  return res.json();
}

async function decidir(
  demandaId: number,
  acao: string,
  body: Record<string, unknown> = {},
): Promise<Demanda> {
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/${acao}/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.json();
}

/** Articulador Estadual. */
export const preAutorizarDemanda = (id: number) => decidir(id, "pre-autorizar");
export const devolverDemanda = (id: number, justificativa: string) =>
  decidir(id, "devolver", { justificativa });

/** UGP. `ajustes`: {id da solicitação: novo valor} — vazio autoriza como pedido. */
export const autorizarDemanda = (id: number, ajustes: Record<number, string> = {}) =>
  decidir(id, "autorizar", { ajustes });
export const recusarDemanda = (id: number, justificativa: string) =>
  decidir(id, "recusar", { justificativa });

/** FGD. `valoresPagos`: {id da solicitação: valor pago}. */
export const atenderDemanda = (id: number) => decidir(id, "atender");
export const concluirDemanda = (id: number, valoresPagos: Record<number, string>) =>
  decidir(id, "concluir", { valores_pagos: valoresPagos });
