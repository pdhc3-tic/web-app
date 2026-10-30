import { apiClient } from "@/app/lib/api";

/**
 * Configuração do mapeamento tipo de solicitação → rubrica (#319), sobre o
 * CRUD da BE-8 (`/api/v1/sgd/config/tipo-rubrica/`, só Super Admin).
 *
 * Um tipo tem no máximo um mapeamento ATIVO; os inativos ficam como
 * histórico. A rubrica é gravada na solicitação quando ela é criada, então
 * trocar o mapeamento não muda as solicitações que já existem.
 */

/** `DemandTypeRubricaMappingSerializer`. */
export type MapeamentoTipoRubrica = {
  id: number;
  tipo: string;
  rubrica: number;
  rubrica_nome: string;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
};

export type MapeamentoPayload = { tipo: string; rubrica: number; ativo: boolean };

/** Rubrica do catálogo do orçamento (pendencias-backend-sprint-11.md, item 1). */
export type Rubrica = { id: number; slug: string; nome: string; ativo: boolean };

const BASE = "/api/v1/sgd/config/tipo-rubrica/";

export const AVISO_NAO_RETROAGE =
  "A alteração vale só para novas solicitações: as já criadas mantêm a rubrica.";

export const ERRO_DUPLICADO = "Já existe um mapeamento ativo para este tipo de solicitação.";

export async function listMapeamentos(
  { incluirInativos }: { incluirInativos: boolean },
  signal?: AbortSignal,
): Promise<MapeamentoTipoRubrica[]> {
  const res = await apiClient(incluirInativos ? BASE : `${BASE}?ativo=true`, { signal });
  return res.json();
}

export async function criarMapeamento(payload: MapeamentoPayload): Promise<MapeamentoTipoRubrica> {
  const res = await apiClient(BASE, { method: "POST", body: JSON.stringify(payload) });
  return res.json();
}

export async function atualizarMapeamento(
  id: number,
  payload: Partial<MapeamentoPayload>,
): Promise<MapeamentoTipoRubrica> {
  const res = await apiClient(`${BASE}${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
  return res.json();
}

export async function removerMapeamento(id: number): Promise<void> {
  await apiClient(`${BASE}${id}/`, { method: "DELETE" });
}

/**
 * `GET /api/v1/sgp/rubricas/` — ainda não existe no backend (pendência 1 da
 * sprint 11). Sem `?ativo=true`, para mostrar o nome de uma rubrica inativa
 * que siga num mapeamento antigo.
 */
export async function listRubricas(signal?: AbortSignal): Promise<Rubrica[]> {
  const res = await apiClient("/api/v1/sgp/rubricas/", { signal });
  return res.json();
}

/**
 * O mapeamento ativo de `tipo` que impediria salvar outro ativo — a mesma
 * regra do `validate` do serializer da BE-8. `idEmEdicao` é o próprio registro
 * sendo editado, que não conflita consigo mesmo.
 */
export function conflitoDeAtivo(
  mapeamentos: readonly MapeamentoTipoRubrica[],
  tipo: string,
  idEmEdicao: number | null,
): MapeamentoTipoRubrica | null {
  return mapeamentos.find((m) => m.ativo && m.tipo === tipo && m.id !== idEmEdicao) ?? null;
}
