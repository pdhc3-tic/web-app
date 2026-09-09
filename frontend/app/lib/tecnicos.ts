import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { SelectOption } from "@/app/components/ui/Select/Select";

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
  qs.set("page", String(Math.floor(params.offset / params.limit) + 1));
  qs.set("page_size", String(params.limit));
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

export async function fetchUserOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  try {
    const res = await apiClient("/api/v1/users/?limit=500&ativo=true", {
      signal,
    });
    const data: Paginated<{ id: number; nome_completo: string }> =
      await res.json();
    return data.results.map((u) => ({
      value: String(u.id),
      label: u.nome_completo,
    }));
  } catch {
    return [];
  }
}
