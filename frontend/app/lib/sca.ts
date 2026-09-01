import { ApiError, apiClient } from "@/app/lib/api";
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
  /**
   * Dia local "YYYY-MM-DD", cru (backend `data_inicio`).
   *
   * Desde a #212 o backend recebe o dia e faz o recorte no TIME_ZONE do
   * servidor — não se converte mais para instante ISO em UTC aqui, que era o
   * que deslocava a janela em 3h.
   */
  iniciadoDe?: string;
  /** Dia local "YYYY-MM-DD", cru (backend `data_fim`). */
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
  if (params.iniciadoDe) qs.set("data_inicio", params.iniciadoDe);
  if (params.iniciadoAte) qs.set("data_fim", params.iniciadoAte);
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
 * Total de dispositivos registrados — número do card da tela-índice do SCA.
 * `page_size=1` porque só interessa o `count` do envelope, mesmo padrão do
 * `fetchUpfCount` do SGP.
 */
export async function fetchDeviceCount(signal?: AbortSignal): Promise<number> {
  const res = await apiClient("/api/v1/sca/devices/?limit=1", { signal });
  const data = (await res.json()) as SyncDevicesPaginated;
  return data.count;
}

/** Opções dos dois selects do log de sincronização, de uma requisição só. */
export type SyncEventsFiltroOptions = {
  dispositivos: SelectOption[];
  tecnicos: SelectOption[];
};

/**
 * Teto real de `SCAPagination` (`max_limit = 100`). Pedir mais que isso é
 * silenciosamente reduzido pelo DRF — era o furo do `?limit=500` anterior, que
 * dava a impressão de trazer tudo numa resposta só.
 */
const SCA_PAGE_LIMIT = 100;

/** Trava de segurança: nenhuma listagem do SCA justifica mais que isto. */
const MAX_PAGINAS = 100;

/** Rótulo estável do técnico — nunca vazio, para o select não ficar mudo. */
function rotuloTecnico(t: SyncDeviceTecnico): string {
  return t.nome?.trim() || t.email || `Técnico ${t.id}`;
}

function ordenarPorRotulo(opcoes: SelectOption[]): SelectOption[] {
  return [...opcoes].sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
}

/**
 * Percorre TODAS as páginas de `/sca/devices/`, seguindo `next` até o fim.
 *
 * Uma resposta não é a lista completa: o `limit` pedido é limitado a 100 pelo
 * `SCAPagination`, então qualquer instalação com mais dispositivos que isso
 * teria a listagem truncada sem aviso.
 */
async function fetchTodosDispositivos(
  signal?: AbortSignal,
): Promise<SyncDeviceListItem[]> {
  const todos: SyncDeviceListItem[] = [];
  let offset = 0;

  for (let pagina = 0; pagina < MAX_PAGINAS; pagina++) {
    const res = await apiClient(
      `/api/v1/sca/devices/?limit=${SCA_PAGE_LIMIT}&offset=${offset}`,
      { signal },
    );
    const data = (await res.json()) as SyncDevicesPaginated;
    todos.push(...data.results);

    // `next` nulo encerra; results vazio protege contra resposta degenerada
    // que manteria o laço girando no mesmo offset.
    if (!data.next || data.results.length === 0) break;
    offset += data.results.length;
  }

  return todos;
}

/**
 * Fonte dedicada de técnicos (`GET /api/v1/sca/tecnicos/`), não paginada e com
 * a mesma permissão das telas irmãs. Cobre também quem tem evento no histórico
 * mas já não tem dispositivo.
 *
 * Devolve `null` — em vez de propagar o erro — quando o endpoint ainda não
 * existe no backend implantado, para o chamador cair no fallback.
 */
async function fetchTecnicosDedicado(
  signal?: AbortSignal,
): Promise<SelectOption[] | null> {
  try {
    const res = await apiClient("/api/v1/sca/tecnicos/", { signal });
    const data = (await res.json()) as SyncDeviceTecnico[];
    return ordenarPorRotulo(
      data.map((t) => ({ value: String(t.id), label: rotuloTecnico(t) })),
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/**
 * Opções de dispositivo e de técnico para os filtros do log (#157).
 *
 * Técnicos vêm de `/api/v1/sca/tecnicos/`, a fonte completa e autorizada: não é
 * paginada e inclui quem só aparece no histórico de eventos, sem dispositivo
 * vinculado. Enquanto esse endpoint não estiver implantado, a função cai num
 * fallback que percorre **todas** as páginas de `/sca/devices/` e deduplica por
 * `tecnico.id` — o que ainda deixa de fora o técnico sem dispositivo, mas nunca
 * trata uma única resposta como lista completa.
 *
 * Por que não `/api/v1/users/`: aquele endpoint é `IsSuperAdmin`, enquanto esta
 * tela é Super Admin **ou** UGP — usá-lo deixaria o select vazio para a UGP.
 */
export async function fetchSyncEventsFiltroOptions(
  signal?: AbortSignal,
): Promise<SyncEventsFiltroOptions> {
  const [tecnicosDedicados, todosDispositivos] = await Promise.all([
    fetchTecnicosDedicado(signal),
    fetchTodosDispositivos(signal),
  ]);

  const dispositivos = todosDispositivos.map((d) => ({
    value: String(d.id),
    label: `${d.nome || d.device_id} · ${rotuloTecnico(d.tecnico)}`,
  }));

  if (tecnicosDedicados) {
    return { dispositivos, tecnicos: tecnicosDedicados };
  }

  const porTecnico = new Map<number, string>();
  for (const d of todosDispositivos) {
    if (!porTecnico.has(d.tecnico.id)) {
      porTecnico.set(d.tecnico.id, rotuloTecnico(d.tecnico));
    }
  }
  const tecnicos = ordenarPorRotulo(
    Array.from(porTecnico, ([id, label]) => ({ value: String(id), label })),
  );

  return { dispositivos, tecnicos };
}
