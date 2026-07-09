import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { Territorio } from "@/app/lib/auth/types";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/sgp/serializers.py::UPFListSerializer. */
export type UpfListItem = {
  id: number;
  nome_titular: string;
  /** Já vem mascarado do backend: "XXX.***.***-XX". */
  cpf: string;
  municipio: string;
  territorio: string | null;
  criado_em: string;
  ativa: boolean;
};

/** Filtro de status mapeado para o parâmetro `ativa` do backend. */
export type StatusUpfFilter = "ativas" | "inativas" | "todas";

export type ListUpfsParams = {
  limit: number;
  offset: number;
  search?: string;
  municipio?: string;
  territorio?: string;
  projeto?: string;
  status?: StatusUpfFilter;
  /** Datas no formato YYYY-MM-DD (input nativo). */
  cadastradoDe?: string;
  cadastradoAte?: string;
  ordering?: string;
};

/** Município para o select de filtro (subset dos campos do endpoint). */
type MunicipalityOption = {
  id: number;
  nome: string;
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function buildUpfsQuery(params: ListUpfsParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));

  if (params.search?.trim()) qs.set("q", params.search.trim());
  if (params.municipio) qs.set("municipio", params.municipio);
  if (params.territorio) qs.set("territorio", params.territorio);
  if (params.projeto) qs.set("projeto", params.projeto);
  if (params.ordering) qs.set("ordering", params.ordering);

  // Status → parâmetro `ativa`.
  // O UPFViewSet só retorna inativas quando `ativa` aparece na query
  // (default: ativa=True). "todas" passa string vazia para desligar o default.
  if (params.status === "ativas") qs.set("ativa", "true");
  else if (params.status === "inativas") qs.set("ativa", "false");
  else if (params.status === "todas") qs.set("ativa", "");

  // Range de "cadastrado em" (datas → datetime ISO em UTC).
  if (params.cadastradoDe) {
    qs.set("criado_em__gte", `${params.cadastradoDe}T00:00:00Z`);
  }
  if (params.cadastradoAte) {
    qs.set("criado_em__lte", `${params.cadastradoAte}T23:59:59Z`);
  }

  return qs.toString();
}

// ─── API ────────────────────────────────────────────────────────────────────

/** GET /api/v1/upfs/?page_size=1 — retorna apenas o total de UPFs no escopo do usuário. */
export async function fetchUpfCount(signal?: AbortSignal): Promise<number> {
  const res = await apiClient("/api/v1/upfs/?page_size=1", { signal });
  const data = (await res.json()) as { count: number };
  return data.count;
}

/** GET /api/v1/upfs/ — listagem paginada com filtros. */
export async function listUpfs(
  params: ListUpfsParams,
  signal?: AbortSignal,
): Promise<Paginated<UpfListItem>> {
  const res = await apiClient(`/api/v1/upfs/?${buildUpfsQuery(params)}`, {
    signal,
  });
  return res.json();
}

/** Opções de município para o filtro (GET /api/v1/municipalities/). */
export async function fetchMunicipalityOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/municipalities/?limit=1000", { signal });
  const data: Paginated<MunicipalityOption> = await res.json();
  return data.results.map((m) => ({
    value: String(m.id),
    label: m.nome,
  }));
}

/** Opções de território para o filtro (GET /api/v1/territories/). */
export async function fetchTerritoryOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/territories/?limit=500&ativo=true", {
    signal,
  });
  const data: Paginated<Territorio> = await res.json();
  return data.results.map((t) => ({
    value: String(t.id),
    label: t.nome,
  }));
}
