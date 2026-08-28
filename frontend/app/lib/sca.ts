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
