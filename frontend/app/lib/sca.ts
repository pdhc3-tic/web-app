import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha o objeto `tecnico` do SyncDeviceListSerializer (User cru). */
export type SyncDeviceTecnico = {
  id: number;
  nome: string;
  email: string;
};

/**
 * Espelha apps/core/serializers.py::TerritorySerializer usado na aninhagem
 * `territorios`. `estados` vem como lista de ids; a listagem SCA só usa `nome`,
 * mas os demais campos são preservados para navegações futuras.
 */
export type SyncDeviceTerritorio = {
  id: number;
  nome: string;
  estados?: number[];
  articulador?: number | null;
  ativo?: boolean;
};

/**
 * Espelha apps/sca/serializers.py::SyncDeviceListSerializer.
 *
 * `ultimo_sync_servidor` é o maior entre `ultimo_push_em` e `ultimo_pull_em`
 * (anotado no queryset); `null` quando o dispositivo nunca sincronizou.
 * `registros_pendentes` é a contagem total agregada por dispositivo.
 */
export type SyncDeviceListItem = {
  id: number;
  device_id: string;
  nome: string;
  modelo: string;
  sistema_operacional: string;
  app_versao: string;
  tecnico: SyncDeviceTecnico;
  territorios: SyncDeviceTerritorio[];
  ultimo_sync_servidor: string | null;
  registros_pendentes: number;
  ativo: boolean;
};

/**
 * Resposta paginada de `/api/v1/sca/devices/` — o backend acrescenta
 * `limiar_alerta_dias` (SystemConfig.sca_sync_alerta_dias, default 7) fora do
 * envelope padrão do DRF; o front usa esse valor para classificar o semáforo.
 */
export type SyncDevicesPaginated = Paginated<SyncDeviceListItem> & {
  limiar_alerta_dias: number;
};

/**
 * Espelha apps/sca/serializers.py::SyncDeviceDetailSerializer.
 *
 * `registros_por_entidade` é um mapa `nome_entidade` → contagem, computado
 * por `services.count_pending_records_by_entity()`. Entidades esperadas na V1:
 * "upf", "member", "activity" — mas o dicionário é mantido aberto para
 * evolução (novas entidades entram sem exigir refactor do tipo).
 */
export type SyncDeviceDetail = SyncDeviceListItem & {
  registros_por_entidade: Record<string, number>;
  criado_em: string;
};

export type ListDevicesParams = {
  limit: number;
  offset: number;
  /** Busca full-text em `user__nome`/`user__email` (backend `search`). */
  search?: string;
  /** Filtro por `user_id` do técnico (backend `tecnico`). */
  tecnico?: number;
  /** Filtro por id de território — mesma semântica de user_territories. */
  territorio?: number;
  /**
   * Campos suportados pelo backend: `ultimo_sync_servidor`, `criado_em`,
   * `nome`, `device_id`. Prefixe com `-` para desc. O default do backend é
   * `ultimo_sync_servidor` ascendente com `nulls_first=True` — dispositivos
   * sem sync ficam no topo.
   */
  ordering?: string;
};

// ─── Semáforo (derivado no front) ────────────────────────────────────────────

/**
 * Estado de conexão de um dispositivo. `status_conexao` NÃO é campo do backend
 * — é calculado aqui a partir de `ultimo_sync_servidor` e `limiar_alerta_dias`,
 * conforme decisão registrada em backend/apps/sca/README.md (V1).
 *
 * - `sem-sync`: nunca sincronizou (`ultimo_sync_servidor === null`);
 * - `vermelho`: última sincronização há mais de `limiar_alerta_dias`;
 * - `laranja`: sync recente, mas com registros pendentes acumulados;
 * - `verde`: sync recente e sem pendências.
 *
 * Precedência: sem-sync > vermelho > laranja > verde.
 */
export type StatusConexao = "verde" | "laranja" | "vermelho" | "sem-sync";

const MS_POR_DIA = 24 * 60 * 60 * 1000;

/**
 * Classifica o status usando `agora` como referência (injetável em teste).
 * `limiarDias` é a janela em dias antes de virar vermelho — vem do payload
 * (`limiar_alerta_dias`) e reflete `SystemConfig.sca_sync_alerta_dias`.
 */
export function statusConexao(
  device: Pick<SyncDeviceListItem, "ultimo_sync_servidor" | "registros_pendentes">,
  limiarDias: number,
  agora: Date = new Date(),
): StatusConexao {
  if (!device.ultimo_sync_servidor) return "sem-sync";
  const t = Date.parse(device.ultimo_sync_servidor);
  if (Number.isNaN(t)) return "sem-sync";
  const diasSemSync = (agora.getTime() - t) / MS_POR_DIA;
  if (diasSemSync > limiarDias) return "vermelho";
  if (device.registros_pendentes > 0) return "laranja";
  return "verde";
}

/** Rótulo curto para o badge do semáforo (pt-BR). */
export function statusLabel(status: StatusConexao): string {
  switch (status) {
    case "verde":
      return "Sincronizado";
    case "laranja":
      return "Pendências";
    case "vermelho":
      return "Sem sync";
    case "sem-sync":
      return "Nunca sincronizou";
  }
}

// ─── API ────────────────────────────────────────────────────────────────────

function buildDevicesQuery(params: ListDevicesParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));
  if (params.search?.trim()) qs.set("search", params.search.trim());
  if (params.tecnico !== undefined) qs.set("tecnico", String(params.tecnico));
  if (params.territorio !== undefined)
    qs.set("territorio", String(params.territorio));
  if (params.ordering) qs.set("ordering", params.ordering);
  return qs.toString();
}

/**
 * GET /api/v1/sca/devices/ — listagem paginada de dispositivos SCA para o
 * painel administrativo (#156). Endpoint é Super Admin / UGP (read-only);
 * outros perfis recebem 403.
 */
export async function listDevices(
  params: ListDevicesParams,
  signal?: AbortSignal,
): Promise<SyncDevicesPaginated> {
  const res = await apiClient(
    `/api/v1/sca/devices/?${buildDevicesQuery(params)}`,
    { signal },
  );
  return res.json();
}

/** GET /api/v1/sca/devices/{id}/ — detalhe do dispositivo (#156). */
export async function getDevice(
  id: number | string,
  signal?: AbortSignal,
): Promise<SyncDeviceDetail> {
  const res = await apiClient(`/api/v1/sca/devices/${id}/`, { signal });
  return res.json();
}

// ─── Sync Events (Log de Sincronização — #157) ──────────────────────────────

/** Espelha SyncEvent.Tipo do backend. */
export type TipoEvento = "push" | "pull" | "refresh";

/**
 * Espelha SyncEvent.TipoConexao. `null` acontece na V1 quando o app não envia
 * o header `X-Connection-Type` (backend/apps/sca/README.md, decisão V1 #2).
 */
export type TipoConexao = "wifi" | "4g" | "3g" | "2g" | "5g" | "offline" | null;

export type SyncEventTecnico = {
  id: number;
  nome: string;
  email: string;
};

/** Dispositivo aninhado no evento — pode ser `null` quando removido. */
export type SyncEventDispositivo = {
  id: number;
  device_id: string;
  nome: string;
};

/** Erro por item retornado no push. Formato definido em sca/README.md. */
export type SyncErroDetalhe = {
  uuid_local: string;
  entidade: string;
  codigo: string;
  mensagem: string;
};

/**
 * Espelha apps/sca/serializers.py::SyncEventListSerializer. `iniciado_em`
 * pode ser `null` para eventos legados sem timestamp de início. `since` só
 * vem preenchido em pulls (marca o cursor pedido pelo cliente).
 */
export type SyncEventListItem = {
  id: number;
  tipo: TipoEvento;
  since: string | null;
  iniciado_em: string | null;
  finalizado_em: string;
  contagem: number;
  contagem_enviados: number;
  contagem_recebidos: number;
  contagem_erros: number;
  has_erros: boolean;
  tipo_conexao: TipoConexao;
  tecnico: SyncEventTecnico;
  dispositivo: SyncEventDispositivo | null;
};

/**
 * Espelha SyncEventDetailSerializer — mesmo do list + `erros_detalhes`
 * (lista de objetos por item rejeitado no push).
 */
export type SyncEventDetail = SyncEventListItem & {
  erros_detalhes: SyncErroDetalhe[];
};

export type ListSyncEventsParams = {
  limit: number;
  offset: number;
  /** ISO datetime (backend `iniciado_em_gte`). */
  iniciadoDe?: string;
  /** ISO datetime (backend `iniciado_em_lte`). */
  iniciadoAte?: string;
  /** User id do técnico. */
  user?: number;
  /** Id do dispositivo (SyncDevice.pk, não device_id). */
  device?: number;
  tipo?: TipoEvento;
  /** Só eventos com erros (backend `com_erro` filter). */
  comErro?: boolean;
  ordering?: string;
};

function buildSyncEventsQuery(params: ListSyncEventsParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));
  if (params.iniciadoDe) qs.set("iniciado_em_gte", params.iniciadoDe);
  if (params.iniciadoAte) qs.set("iniciado_em_lte", params.iniciadoAte);
  if (params.user !== undefined) qs.set("user", String(params.user));
  if (params.device !== undefined) qs.set("device", String(params.device));
  if (params.tipo) qs.set("tipo", params.tipo);
  if (params.comErro !== undefined)
    qs.set("com_erro", params.comErro ? "true" : "false");
  if (params.ordering) qs.set("ordering", params.ordering);
  return qs.toString();
}

/** GET /api/v1/sca/sync-events/ — histórico paginado (#157). Super Admin/UGP. */
export async function listSyncEvents(
  params: ListSyncEventsParams,
  signal?: AbortSignal,
): Promise<Paginated<SyncEventListItem>> {
  const res = await apiClient(
    `/api/v1/sca/sync-events/?${buildSyncEventsQuery(params)}`,
    { signal },
  );
  return res.json();
}

/** GET /api/v1/sca/sync-events/{id}/ — detalhe com `erros_detalhes`. */
export async function getSyncEvent(
  id: number | string,
  signal?: AbortSignal,
): Promise<SyncEventDetail> {
  const res = await apiClient(`/api/v1/sca/sync-events/${id}/`, { signal });
  return res.json();
}

// ─── Filtros (opções para os selects) ────────────────────────────────────────

/**
 * Opções de território para o filtro. Reaproveita `/api/v1/territories/`;
 * mantém-se local para o painel SCA (o helper de users.ts trabalha só com
 * ativos por default, e aqui a lista completa importa para contexto histórico).
 */
export async function fetchScaTerritoryOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/territories/?limit=500", { signal });
  const data: Paginated<SyncDeviceTerritorio> = await res.json();
  return data.results.map((t) => ({ value: String(t.id), label: t.nome }));
}

/**
 * Opções de dispositivo para o filtro do log (#157). Não há um endpoint
 * dedicado a "listar todos os dispositivos como options"; reaproveita o
 * próprio `/api/v1/sca/devices/` com limit alto — a mesma listagem que o
 * painel #156 já consome, então cache de HTTP costuma bater.
 */
export async function fetchDispositivoOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/sca/devices/?limit=500", { signal });
  const data = (await res.json()) as SyncDevicesPaginated;
  return data.results.map((d) => ({
    value: String(d.id),
    label: `${d.nome || d.device_id} · ${d.tecnico.nome}`,
  }));
}
