import { apiClient } from "@/app/lib/api";

/** GET /api/v1/upfs/?page_size=1 — retorna apenas o total de UPFs no escopo do usuário. */
export async function fetchUpfCount(signal?: AbortSignal): Promise<number> {
  const res = await apiClient("/api/v1/upfs/?page_size=1", { signal });
  const data = (await res.json()) as { count: number };
  return data.count;
}
