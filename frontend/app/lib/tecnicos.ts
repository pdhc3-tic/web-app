import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { SelectOption } from "@/app/components/ui/Select/Select";

export type UsuarioElegivel = {
  id: number;
  nome_completo: string;
  email: string;
};

export type TecnicoListItem = {
  id: number;
  user: number;
  user_nome: string;
  territorio: number | null;
  territorio_nome: string | null;
  osc: number | null;
  osc_nome: string | null;
  papel: string;
  ativo: boolean;
};

export type TecnicoWritePayload = {
  user: number;
  territorio: number | null;
  osc: number | null;
  papel: string;
};

export type ListTecnicosSGPParams = {
  limit: number;
  offset: number;
  territorio?: string;
  osc?: string;
  papel?: string;
  ativo?: string;
};

function buildQuery(params: ListTecnicosSGPParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));
  if (params.territorio) qs.set("territorio", params.territorio);
  if (params.osc) qs.set("osc", params.osc);
  if (params.papel) qs.set("papel", params.papel);
  if (params.ativo) qs.set("ativo", params.ativo);
  return qs.toString();
}

export async function listTecnicosSGP(
  params: ListTecnicosSGPParams,
  signal?: AbortSignal,
): Promise<Paginated<TecnicoListItem>> {
  const res = await apiClient(`/api/v1/sgp/tecnicos/?${buildQuery(params)}`, {
    signal,
  });
  return res.json();
}

export async function createTecnico(
  payload: TecnicoWritePayload,
): Promise<TecnicoListItem> {
  const res = await apiClient("/api/v1/sgp/tecnicos/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function updateTecnico(
  id: number,
  payload: Partial<TecnicoWritePayload>,
): Promise<TecnicoListItem> {
  const res = await apiClient(`/api/v1/sgp/tecnicos/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function deactivateTecnico(id: number): Promise<void> {
  await apiClient(`/api/v1/sgp/tecnicos/${id}/`, { method: "DELETE" });
}

export async function fetchOscOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  try {
    const res = await apiClient("/api/v1/organizations/?limit=500", { signal });
    const data: Paginated<{ id: number; nome: string }> = await res.json();
    return data.results.map((o) => ({ value: String(o.id), label: o.nome }));
  } catch {
    return [];
  }
}

/**
 * Busca de usuários elegíveis a técnico (A2 da #302): usuários ativos sem
 * vínculo em `Tecnico`, retornados pelo backend em `GET
 * /api/v1/sgp/tecnicos/usuarios-elegiveis/?q=`. Troca o `fetchUserOptions()`
 * antigo (`/users/?limit=500`), que era restrito ao Super Admin e cortava a
 * lista em 500. A busca é no servidor para a cadastradora que começa com
 * centenas de usuários.
 */
export async function searchUsuariosElegiveis(
  q: string,
  signal?: AbortSignal,
): Promise<UsuarioElegivel[]> {
  const qs = new URLSearchParams();
  if (q.trim()) qs.set("q", q.trim());
  qs.set("limit", "20");
  const url = qs.toString()
    ? `/api/v1/sgp/tecnicos/usuarios-elegiveis/?${qs}`
    : "/api/v1/sgp/tecnicos/usuarios-elegiveis/";
  const res = await apiClient(url, { signal });
  const data: Paginated<UsuarioElegivel> = await res.json();
  return data.results;
}
