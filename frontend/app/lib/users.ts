import { apiClient } from "@/app/lib/api";
import type { Perfil, Territorio } from "@/app/lib/auth/types";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Autor de uma revogação — `acesso_revogado_por` do UserListSerializer. */
export type RevogadoPor = {
  id: number;
  nome: string;
};

/** Espelha apps/core/serializers.py::UserListSerializer. */
export type UserListItem = {
  id: number;
  nome_completo: string;
  email: string;
  perfis: Perfil[];
  territorios: Territorio[];
  ativo: boolean;
  ultimo_login: string | null;
  /**
   * Wipe remoto pendente: o app SCA apaga os dados locais no próximo sync e
   * exige novo login. Independe de `ativo` — um usuário revogado continua
   * ativo, então ele não some da listagem default (que filtra `ativo=true`).
   */
  acesso_revogado: boolean;
  acesso_revogado_em: string | null;
  acesso_revogado_por: RevogadoPor | null;
  /**
   * Só vêm preenchidos com `?com_dispositivo=true` — o backend anota os
   * agregados apenas nesse caso, para não pagar o N+1 nas demais listagens
   * (apps/core/views/users.py::UserViewSet.get_queryset).
   */
  qtd_dispositivos: number | null;
  ultimo_sync_dispositivos: string | null;
};

/** Resposta paginada padrão do DRF (LimitOffsetPagination). */
export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

/** Filtro de status mapeado para o parâmetro `ativo` do backend. */
export type StatusFilter = "ativos" | "inativos" | "todos";

export type ListUsersParams = {
  limit: number;
  offset: number;
  search?: string;
  perfil?: string;
  territorio?: string;
  status?: StatusFilter;
  /** Datas no formato YYYY-MM-DD (input nativo). */
  ultimoAcessoDe?: string;
  ultimoAcessoAte?: string;
  ordering?: string;
  /**
   * Restringe aos usuários com ao menos um dispositivo SCA vinculado e liga os
   * agregados `qtd_dispositivos` / `ultimo_sync_dispositivos`.
   */
  comDispositivo?: boolean;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function buildUsersQuery(params: ListUsersParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));

  if (params.search?.trim()) qs.set("search", params.search.trim());
  if (params.perfil) qs.set("perfil", params.perfil);
  if (params.territorio) qs.set("territorio", params.territorio);
  if (params.ordering) qs.set("ordering", params.ordering);
  if (params.comDispositivo) qs.set("com_dispositivo", "true");

  // Status → parâmetro `ativo`.
  // O backend só lista inativos quando `ativo` está presente na query
  // (caso contrário filtra ativo=True por padrão). Passar string vazia
  // mantém o parâmetro presente sem aplicar filtro → retorna todos.
  if (params.status === "ativos") qs.set("ativo", "true");
  else if (params.status === "inativos") qs.set("ativo", "false");
  else if (params.status === "todos") qs.set("ativo", "");

  // Range de último acesso (datas → datetime ISO em UTC).
  if (params.ultimoAcessoDe) {
    qs.set("ultimo_login_gte", `${params.ultimoAcessoDe}T00:00:00Z`);
  }
  if (params.ultimoAcessoAte) {
    qs.set("ultimo_login_lte", `${params.ultimoAcessoAte}T23:59:59Z`);
  }

  return qs.toString();
}

// ─── API ────────────────────────────────────────────────────────────────────

/** GET /api/v1/users/ — listagem paginada (restrito a Super Admin no BE). */
export async function listUsers(
  params: ListUsersParams,
  signal?: AbortSignal,
): Promise<Paginated<UserListItem>> {
  const res = await apiClient(`/api/v1/users/?${buildUsersQuery(params)}`, {
    signal,
  });
  return res.json();
}

// ─── Acesso ao app SCA (revogar / reativar) ─────────────────────────────────

/**
 * Corpo devolvido por `revogar-acesso/` e `reativar-acesso/`.
 *
 * `message` já vem em pt-BR e descreve a consequência (wipe no próximo sync /
 * necessidade de novo login) — a tela usa esse texto direto no toast em vez de
 * manter uma segunda cópia da copy do lado do cliente.
 */
export type AcessoResponse = {
  message: string;
  acesso_revogado: boolean;
  /** Refresh tokens colocados na blacklist — todas as sessões do usuário. */
  sessoes_invalidadas: number;
};

/**
 * PATCH /api/v1/users/{id}/revogar-acesso/ — marca `acesso_revogado` e derruba
 * as sessões ativas. O apagamento dos dados locais acontece no próximo sync do
 * dispositivo; o efeito no servidor é imediato.
 */
export async function revogarAcesso(
  id: number,
  signal?: AbortSignal,
): Promise<AcessoResponse> {
  const res = await apiClient(`/api/v1/users/${id}/revogar-acesso/`, {
    method: "PATCH",
    signal,
  });
  return res.json();
}

/**
 * PATCH /api/v1/users/{id}/reativar-acesso/ — limpa a revogação. O backend
 * invalida as sessões de novo, então o técnico precisa de um login completo.
 */
export async function reativarAcesso(
  id: number,
  signal?: AbortSignal,
): Promise<AcessoResponse> {
  const res = await apiClient(`/api/v1/users/${id}/reativar-acesso/`, {
    method: "PATCH",
    signal,
  });
  return res.json();
}

/** Opções de perfil para o filtro (GET /api/v1/roles/). */
export async function fetchRoleOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/roles/?limit=200&ativo=true", {
    signal,
  });
  const data: Paginated<Perfil> = await res.json();
  return data.results.map((r) => ({
    value: String(r.id),
    label: r.nome,
  }));
}

/** Opções de território para o filtro (GET /api/v1/territories/). */
export async function fetchTerritoryOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/territories/?limit=500", { signal });
  const data: Paginated<Territorio> = await res.json();
  return data.results.map((t) => ({
    value: String(t.id),
    label: t.nome,
  }));
}
