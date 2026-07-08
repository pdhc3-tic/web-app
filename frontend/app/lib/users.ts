import { apiClient } from "@/app/lib/api";
import type { Perfil, Territorio } from "@/app/lib/auth/types";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/core/serializers.py::UserListSerializer. */
export type UserListItem = {
  id: number;
  nome_completo: string;
  email: string;
  perfis: Perfil[];
  territorios: Territorio[];
  ativo: boolean;
  ultimo_login: string | null;
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
