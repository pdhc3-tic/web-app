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

/** `ApprovalStepSerializer` — uma decisão na linha do tempo da demanda. */
export type EtapaDemanda = {
  id: number;
  etapa: "pre_autorizacao" | "autorizacao" | "atendimento" | "cancelamento";
  etapa_display: string;
  acao: "aprovado" | "recusado" | "devolvido" | "atendido" | "cancelado";
  acao_display: string;
  responsavel_nome: string | null;
  justificativa: string;
  excedente_autorizado: boolean;
  criado_em: string;
};

/**
 * Risco de glosa — `GlosaRiskSerializer` de `GET /sgp/glosa-riscos/` (#391,
 * pedido da #408). `pago_acima_autorizado` traz a solicitação e os valores
 * pago e autorizado; `demanda_sem_evidencia` vem da conclusão sem evidência
 * da atividade e só tem o valor exposto.
 */
export type RiscoGlosa = {
  id: number;
  tipo: "pago_acima_autorizado" | "demanda_sem_evidencia";
  severidade: "alta" | "media" | "baixa";
  valor_exposto: string;
  activity_id: number | null;
  demanda_id: number;
  demand_request_id: number | null;
  valor_autorizado: string | null;
  valor_pago: string | null;
  criado_em: string;
  resolvido_em: string | null;
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
  solicitante_nome: string;
  /**
   * Abrangência territorial (#352): estado e território do SOLICITANTE,
   * gravados na criação e congelados. Definem o Articulador que analisa, a
   * fila e o pool de saldo — a atividade não entra no critério. Os três nulos
   * = demanda de nível nacional (solicitante sem território, como o Super
   * Admin). `contexto.territorio_*` também passou a ser o da demanda.
   */
  estado_sigla: string | null;
  territorio: number | null;
  territorio_nome: string | null;
  /** A atividade acontece em outro estado que não o da demanda. */
  atividade_fora_do_territorio: boolean;
  /** Decisões em ordem cronológica (pré-autorização, autorização, atendimento). */
  etapas: EtapaDemanda[];
  criado_em: string;
  atualizado_em: string;
};

/**
 * "Território X (PB)", só o estado, ou "Nacional" — a abrangência como o
 * backend gravou, sem recalcular nada.
 */
export function rotuloAbrangencia(
  demanda: Pick<Demanda, "estado_sigla" | "territorio_nome">,
): string {
  if (demanda.territorio_nome) {
    return demanda.estado_sigla
      ? `${demanda.territorio_nome} (${demanda.estado_sigla})`
      : demanda.territorio_nome;
  }
  return demanda.estado_sigla ?? "Nacional";
}

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
 * A listagem de demandas é paginada (`DemandPagination`, BE-5): sem `limit`,
 * viriam só as 10 primeiras. As telas pedem o teto do backend (`max_limit`
 * = 200) e recebem o total, para avisar quando há mais do que a página trouxe.
 */
const LIMITE_LISTA_DEMANDAS = 200;

/** Página padrão do painel de demandas (#323), que navega pela listagem página a página. */
export const DEMANDAS_POR_PAGINA = 50;

export type PaginaDemandas = { offset: number; limit: number };

export type ListaDemandas = {
  demandas: Demanda[];
  /** Total no backend com os mesmos filtros; maior que `demandas.length` = lista parcial. */
  total: number;
};

async function lerListaDemandas(
  qs: URLSearchParams,
  signal?: AbortSignal,
  pagina?: PaginaDemandas,
): Promise<ListaDemandas> {
  qs.set("limit", String(pagina?.limit ?? LIMITE_LISTA_DEMANDAS));
  if (pagina?.offset) qs.set("offset", String(pagina.offset));
  const res = await apiClient(`${DEMANDAS_PATH}?${qs}`, { signal });
  const resposta = (await res.json()) as { count: number; results: Demanda[] };
  return { demandas: resposta.results, total: resposta.count };
}

/** GET /api/v1/sgd/demandas/?atividade={id} — as demandas de uma atividade. */
export async function listDemandasDaAtividade(
  atividadeId: number | string,
  signal?: AbortSignal,
): Promise<ListaDemandas> {
  return lerListaDemandas(new URLSearchParams({ atividade: String(atividadeId) }), signal);
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
  /** `MunicipioNestedSerializer`: o estado vem embutido (#226). */
  municipio: { id: number; nome: string; estado?: { sigla: string } | null };
  tecnico_nome?: string;
};

/**
 * GET /api/v1/sgp/atividades/?status=planejado&status=agendado&q={texto}
 * — atividades que aceitam demanda, para o campo com busca. `status`
 * repetido e `q` pelo título são do `ActivityFilter` (PR #328).
 *
 * Sem `tecnico_id` desde a #361: a demanda pode ser vinculada a qualquer
 * atividade, de outro técnico ou de outro estado (#352) — a abrangência vem
 * de quem cria. O recorte que sobra é o territorial da própria rota do SGP,
 * que ainda esconde as atividades de outros estados
 * (docs/pendencias-backend-sprint-12a.md).
 */
export async function buscarAtividadesElegiveis(
  params: { busca: string },
  signal?: AbortSignal,
): Promise<AtividadeElegivel[]> {
  const qs = new URLSearchParams();
  for (const s of STATUS_ATIVIDADE_ELEGIVEIS) qs.append("status", s);
  if (params.busca.trim()) qs.set("q", params.busca.trim());
  qs.set("ordering", "data_inicio");
  qs.set("page_size", "20");

  const res = await apiClient(`/api/v1/sgp/atividades/?${qs}`, { signal });
  const data: { results: AtividadeElegivel[] } = await res.json();
  return data.results;
}

// ─── Painel de decisão (#296) ────────────────────────────────────────────────

/**
 * Fila "Aguardando minha ação" — `GET .../aguardando-minha-acao/contagem/`.
 * A regra de quais status cabem a cada perfil mora no backend
 * (`status_aguardando_acao`); a tela usa o `status` devolvido aqui para
 * listar a fila, sem espelhar a regra.
 */
export type ContagemFila = { total: number; status: StatusDemanda[] };

export async function fetchContagemFila(signal?: AbortSignal): Promise<ContagemFila> {
  const res = await apiClient(`${DEMANDAS_PATH}aguardando-minha-acao/contagem/`, { signal });
  return res.json();
}

/**
 * Campos aceitos pelo `ORDENACOES_DA_LISTAGEM` do `DemandViewSet` (BE-10).
 * O `-` prefixa a ordem decrescente, no padrão do `ordering` do DRF.
 */
export type OrdenacaoDemandas = "valor_estimado_total" | "-valor_estimado_total";

/**
 * GET /api/v1/sgd/demandas/ — listagem, já no escopo do perfil (o Articulador
 * só enxerga as Submetidas do próprio estado).
 *
 * - `status`: vários vão como parâmetro repetido, e o backend devolve a união.
 * - `aguardandoMinhaAcao`: a fila do perfil logado, pela mesma regra da
 *   contagem (`aguardando-minha-acao/contagem/`) — o `count` da lista bate com
 *   o `total` do badge.
 * - `filtros`: os do `DemandFilter` do BE-5 (atividade, ação, território,
 *   período…) — o drill-down do painel de execução (#297) leva o recorte do
 *   painel para a lista mostrar as demandas que compõem o custo exibido.
 * - `ordenacao`: por `valor_estimado_total` do servidor (BE-10). Sem ela, o
 *   backend usa `-criado_em`.
 * - `pagina`: `offset`/`limit` do `DemandPagination`. Sem ela, vem a página
 *   cheia do backend (200).
 */
export async function listDemandas(
  params: {
    status?: StatusDemanda[];
    aguardandoMinhaAcao?: boolean;
    filtros?: Record<string, string | undefined>;
    ordenacao?: OrdenacaoDemandas;
    pagina?: PaginaDemandas;
  } = {},
  signal?: AbortSignal,
): Promise<ListaDemandas> {
  const qs = new URLSearchParams();
  for (const st of params.status ?? []) qs.append("status", st);
  if (params.aguardandoMinhaAcao) qs.set("aguardando_minha_acao", "true");
  for (const [chave, valor] of Object.entries(params.filtros ?? {})) {
    if (valor) qs.set(chave, valor);
  }
  if (params.ordenacao) qs.set("ordering", params.ordenacao);
  return lerListaDemandas(qs, signal, params.pagina);
}

/** GET /api/v1/sgd/demandas/{id}/ */
export async function getDemanda(id: number | string, signal?: AbortSignal): Promise<Demanda> {
  const res = await apiClient(`${DEMANDAS_PATH}${id}/`, { signal });
  return res.json();
}

/**
 * GET /api/v1/sgp/glosa-riscos/?demanda={id} — os riscos de glosa da demanda,
 * em ordem cronológica (#360). A rota é paginada (10 por padrão); uma demanda
 * tem poucos riscos, então uma página de 100 traz todos. Só Super Admin, UGP,
 * FGD e Articulador acessam (`canVerRiscosDeGlosa`).
 */
export async function listRiscosDeGlosa(demandaId: number, signal?: AbortSignal): Promise<RiscoGlosa[]> {
  const qs = new URLSearchParams({ demanda: String(demandaId), limit: "100" });
  const res = await apiClient(`/api/v1/sgp/glosa-riscos/?${qs}`, { signal });
  const corpo = (await res.json()) as { results: RiscoGlosa[] } | RiscoGlosa[];
  return Array.isArray(corpo) ? corpo : corpo.results;
}

/**
 * GET /api/v1/sgp/glosa-riscos/?activity={id} — os riscos de glosa da atividade,
 * do maior valor exposto para o menor (#404). Mesmos perfis de
 * `listRiscosDeGlosa` e, como ela, uma página de 100: uma atividade tem poucos
 * riscos.
 *
 * A rota não filtra os riscos em aberto, então a ficha descarta os resolvidos
 * (`riscosAbertos`). Pedir só os abertos ao servidor é o item 7 do
 * `docs/pendencias-backend-sprint-12b.md`.
 */
export async function listRiscosDeGlosaDaAtividade(
  atividadeId: number,
  signal?: AbortSignal,
): Promise<RiscoGlosa[]> {
  const qs = new URLSearchParams({ activity: String(atividadeId), limit: "100" });
  const res = await apiClient(`/api/v1/sgp/glosa-riscos/?${qs}`, { signal });
  const corpo = (await res.json()) as { results: RiscoGlosa[] } | RiscoGlosa[];
  return Array.isArray(corpo) ? corpo : corpo.results;
}

export const TIPO_RISCO_GLOSA_LABEL: Record<RiscoGlosa["tipo"], string> = {
  pago_acima_autorizado: "Pago acima do autorizado",
  demanda_sem_evidencia: "Demanda executada sem evidência",
};

export const SEVERIDADE_GLOSA_LABEL: Record<RiscoGlosa["severidade"], string> = {
  alta: "Alta",
  media: "Média",
  baixa: "Baixa",
};

/** Só os riscos em aberto contam para o bloco da ficha: resolvido não é mais risco. */
export function riscosAbertos(riscos: RiscoGlosa[] | undefined): RiscoGlosa[] {
  return (riscos ?? []).filter((r) => r.resolvido_em === null);
}

/** Soma do valor exposto, em centavos para não acumular erro de ponto flutuante. */
export function totalExposto(riscos: RiscoGlosa[]): string {
  const centavos = riscos.reduce((soma, r) => soma + Math.round(Number(r.valor_exposto) * 100), 0);
  return (centavos / 100).toFixed(2);
}

// ─── Auditoria (#322, BE-7) ──────────────────────────────────────────────────

/**
 * Uma entrada da trilha de auditoria de uma demanda — mudança de status ou
 * movimentação de saldo. Espelha `DemandAuditEntrySerializer`
 * (`apps/sgd/serializers/auditoria.py`).
 */
export type EventoAuditoria = {
  id: number;
  /**
   * "status" para transições da demanda, "saldo" para movimentações do SGP e
   * "recurso_extra" para o pedido de recurso extra (inclui o aumento de limite
   * e o remanejamento que ele gera).
   */
  tipo: "status" | "saldo" | "recurso_extra";
  /** Ex.: `demanda.criada`, `demanda.status_alterado`, `saldo.reserva`. */
  acao: string;
  /** Nulo quando a transição é do sistema (cancelamento automático). */
  usuario: { id: number; nome: string } | null;
  /** Só para o Super Admin; nulo para os demais perfis. */
  ip: string | null;
  timestamp: string;
  valores_anteriores: Record<string, unknown>;
  valores_novos: Record<string, unknown>;
};

export type PaginaAuditoria = {
  resultados: EventoAuditoria[];
  /** Total no backend; a lista entregue é parcial enquanto `proxima_offset` existir. */
  total: number;
  /** Próximo `offset` a pedir, ou null quando acabou. */
  proxima_offset: number | null;
};

/** Tamanho de página da trilha; o backend aceita `limit`/`offset` (BE-10). */
export const AUDITORIA_PAGINA = 20;

/**
 * GET /api/v1/sgd/demandas/{id}/auditoria/?limit=&offset=
 *
 * Backend: `AuditLogPagination` (default 20, max 100) em `DemandViewSet.auditoria`.
 * Quem vê a demanda vê a trilha; `ip` só vem preenchido para o Super Admin.
 */
export async function listAuditoriaDemanda(
  demandaId: number | string,
  params: { offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<PaginaAuditoria> {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit ?? AUDITORIA_PAGINA));
  if (params.offset) qs.set("offset", String(params.offset));
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/auditoria/?${qs}`, { signal });
  const pagina = (await res.json()) as {
    count: number;
    next: string | null;
    results: EventoAuditoria[];
  };
  const consumidos = (params.offset ?? 0) + pagina.results.length;
  return {
    resultados: pagina.results,
    total: pagina.count,
    proxima_offset: pagina.next ? consumidos : null,
  };
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
  trava_bloqueada: "individual" | "territorial" | "origem" | null;
  individual: ImpactoTrava;
  territorial: ImpactoTrava;
  /** Só com `origem_allocation`: o efeito do excedente no pool de origem. */
  origem?: ImpactoOrigem | null;
};

/** Efeito da autorização com excedente no pool de origem (#363). */
export type ImpactoOrigem = {
  id: number;
  valor_remanejado: number | string;
  fora_do_limite: number | string;
  saldo_antes: number | string;
  saldo_apos: number | string;
  semaforo_antes: FaixaSemaforo | null;
  semaforo_apos: FaixaSemaforo | null;
};

/**
 * GET /api/v1/sgd/demandas/{id}/preview-decisao/?demand_request_id=&valor=
 * `valor` é o valor que a decisão vai reservar para a solicitação. Com
 * `origemAllocation`, simula a autorização com excedente coberto por ela.
 */
export async function previewDecisao(
  demandaId: number,
  solicitacaoId: number,
  valor: string,
  origemAllocation: string,
  signal?: AbortSignal,
): Promise<PreviewDecisao> {
  const qs = new URLSearchParams({ demand_request_id: String(solicitacaoId), valor });
  if (origemAllocation) qs.set("origem_allocation", origemAllocation);
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

/**
 * UGP. `ajustes`: {id da solicitação: novo valor} — vazio autoriza como pedido.
 * `excedente`: o que passar do limite ou do pool sai do pool de origem (#384).
 */
export const autorizarDemanda = (
  id: number,
  ajustes: Record<number, string> = {},
  excedente?: { origemAllocation: number; justificativa: string },
) =>
  decidir(id, "autorizar", {
    ajustes,
    ...(excedente && {
      excedente_autorizado: true,
      origem_allocation: excedente.origemAllocation,
      justificativa: excedente.justificativa,
    }),
  });
export const recusarDemanda = (id: number, justificativa: string) =>
  decidir(id, "recusar", { justificativa });

/** FGD. `valoresPagos`: {id da solicitação: valor pago}. */
export const atenderDemanda = (id: number) => decidir(id, "atender");
/** Quanto o valor pago passa do autorizado; `null` se não passa ou se o campo está vazio. */
export function excedenteDoPago(pago: string, autorizado: string): number | null {
  const centavos = (valor: string) => Math.round(Number(valor) * 100);
  const diferenca = centavos(pago) - centavos(autorizado);
  return pago.trim() !== "" && diferenca > 0 ? diferenca / 100 : null;
}

export const concluirDemanda = (id: number, valoresPagos: Record<number, string>) =>
  decidir(id, "concluir", { valores_pagos: valoresPagos });

/**
 * UGP e Super Admin, em Autorizada. O backend libera as reservas de saldo e
 * grava a etapa de cancelamento, que já volta em `etapas`.
 */
export const cancelarDemanda = (id: number, justificativa: string) =>
  decidir(id, "cancelar", { justificativa });
