import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";

// ─── Constantes espelhadas do backend ────────────────────────────────────────

/** Espelha apps/sgp/models/production.py::Production.TIPO_CHOICES. */
export const TIPO_OPTIONS = [
  { value: "agricola", label: "Agrícola" },
  { value: "pecuaria", label: "Pecuária" },
  { value: "outra", label: "Outra" },
] as const;

export type TipoProducao = (typeof TIPO_OPTIONS)[number]["value"];

/** Espelha Production.SISTEMA_CRIACAO_CHOICES. */
export const SISTEMA_CRIACAO_OPTIONS = [
  { value: "extensivo", label: "Extensivo" },
  { value: "semi_intensivo", label: "Semi-intensivo" },
  { value: "intensivo", label: "Intensivo" },
] as const;

export type SistemaCriacao = (typeof SISTEMA_CRIACAO_OPTIONS)[number]["value"];

/** Espelha Production.TIPO_OUTRA_CHOICES. */
export const TIPO_OUTRA_OPTIONS = [
  { value: "artesanato", label: "Artesanato" },
  { value: "beneficiamento", label: "Beneficiamento" },
  { value: "extrativismo", label: "Extrativismo" },
  { value: "outro", label: "Outro" },
] as const;

export type TipoOutra = (typeof TIPO_OUTRA_OPTIONS)[number]["value"];

// Categorias chegam como valor cru do choice ("graos", "ovino") e a UI exibe o
// rótulo, então a tradução acontece na fronteira da API — ver toCatalogoItem().

/** Espelha apps/sgp/models/catalogos.py::Cultura.CATEGORIA_CHOICES. */
const CULTURA_CATEGORIA_LABELS: Record<string, string> = {
  graos: "Grãos",
  raizes: "Raízes",
  frutas: "Frutas",
  hortalicas: "Hortaliças",
  leguminosas: "Leguminosas",
  oleaginosas: "Oleaginosas",
  fibrosas: "Fibrosas",
  forrageiras: "Forrageiras",
  ornamentais: "Ornamentais",
  medicinais: "Medicinais",
  outras: "Outras",
};

/** Espelha EspecieAnimal.CATEGORIA_CHOICES. */
const ESPECIE_CATEGORIA_LABELS: Record<string, string> = {
  bovino: "Bovino",
  suino: "Suíno",
  ovino: "Ovino",
  caprino: "Caprino",
  aves: "Aves",
  equino: "Equino",
  piscicultura: "Piscicultura",
  apicultura: "Apicultura",
  outros: "Outros",
};

/** Produção usa a LimitOffsetPagination padrão do DRF (PAGE_SIZE=10). */
const LIMITE_PRODUCOES = 100;
/** Catálogos usam CatalogoPagination (PageNumberPagination, max_page_size=200). */
const TAMANHO_PAGINA_CATALOGO = 50;

// ─── Tipos ───────────────────────────────────────────────────────────────────

/** Cultura ou espécie animal, com `categoria` já traduzida para exibição. */
export type CatalogoItem = {
  id: number;
  nome: string;
  categoria: string;
};

/** Espelha apps/sgp/serializers.py::ProductionSerializer (leitura). */
export type Producao = {
  id: number;
  tipo: TipoProducao;

  cultura: CatalogoItem | null;
  area_ha: string | null;
  producao_estimada: string | null;
  unidade_producao: string | null;
  sementes_crioulas: boolean;

  especie: CatalogoItem | null;
  n_matrizes: number | null;
  n_reprodutores: number | null;
  n_jovens: number | null;
  area_pastejo_ha: string | null;
  sistema_criacao: SistemaCriacao | null;

  tipo_outra: TipoOutra | null;
  descricao_outra: string | null;
  quantidade_produzida: string | null;
  renda_estimada_mensal: string | null;

  custo_anual: string | null;
  observacoes: string | null;
};

/** Campos graváveis (POST/PATCH). As FKs vão como `cultura_id` / `especie_id`. */
export type ProducaoWritePayload = {
  tipo: TipoProducao;

  cultura_id?: number | null;
  area_ha?: string | null;
  producao_estimada?: string | null;
  unidade_producao?: string | null;
  sementes_crioulas?: boolean;

  especie_id?: number | null;
  n_matrizes?: number | null;
  n_reprodutores?: number | null;
  n_jovens?: number | null;
  area_pastejo_ha?: string | null;
  sistema_criacao?: SistemaCriacao | null;

  tipo_outra?: TipoOutra | null;
  descricao_outra?: string | null;
  quantidade_produzida?: string | null;
  renda_estimada_mensal?: string | null;

  custo_anual?: string | null;
  observacoes?: string | null;
};

/** Forma crua devolvida pela API, antes da tradução de `categoria`. */
type CatalogoApiItem = { id: number; nome: string; categoria: string };

type ProducaoApi = Omit<Producao, "cultura" | "especie"> & {
  cultura: CatalogoApiItem | null;
  especie: CatalogoApiItem | null;
};

// ─── Normalização ────────────────────────────────────────────────────────────

function toCatalogoItem(
  raw: CatalogoApiItem,
  labels: Record<string, string>,
): CatalogoItem {
  return {
    id: raw.id,
    nome: raw.nome,
    categoria: labels[raw.categoria] ?? raw.categoria,
  };
}

function toProducao(raw: ProducaoApi): Producao {
  return {
    ...raw,
    cultura: raw.cultura ? toCatalogoItem(raw.cultura, CULTURA_CATEGORIA_LABELS) : null,
    especie: raw.especie ? toCatalogoItem(raw.especie, ESPECIE_CATEGORIA_LABELS) : null,
  };
}

/**
 * Em PATCH, os campos ausentes do payload permanecem com o valor anterior. Ao
 * trocar o tipo (agrícola → pecuária, p.ex.) a FK antiga sobreviveria e o
 * ProductionSerializer.validate rejeitaria ("Cultura deve ser nula para produção
 * pecuária"). Zeramos explicitamente o que não pertence ao tipo enviado.
 */
function comCamposDeOutrosTiposZerados(
  payload: ProducaoWritePayload,
): ProducaoWritePayload {
  return {
    cultura_id: null,
    especie_id: null,
    tipo_outra: null,
    ...payload,
  };
}

// ─── API ─────────────────────────────────────────────────────────────────────

/** GET /api/v1/upfs/{upfId}/producao/ — atividades produtivas da UPF. */
export async function listProducoes(
  upfId: string,
  signal?: AbortSignal,
): Promise<Producao[]> {
  const res = await apiClient(
    `/api/v1/upfs/${upfId}/producao/?limit=${LIMITE_PRODUCOES}`,
    { signal },
  );
  const data: Paginated<ProducaoApi> = await res.json();
  return data.results.map(toProducao);
}

/** POST /api/v1/upfs/{upfId}/producao/ — cria uma atividade produtiva. */
export async function createProducao(
  upfId: string,
  payload: ProducaoWritePayload,
): Promise<Producao> {
  const res = await apiClient(`/api/v1/upfs/${upfId}/producao/`, {
    method: "POST",
    body: JSON.stringify(comCamposDeOutrosTiposZerados(payload)),
  });
  return toProducao(await res.json());
}

/** PATCH /api/v1/upfs/{upfId}/producao/{id}/ — atualiza uma atividade produtiva. */
export async function updateProducao(
  upfId: string,
  id: number,
  payload: ProducaoWritePayload,
): Promise<Producao> {
  const res = await apiClient(`/api/v1/upfs/${upfId}/producao/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(comCamposDeOutrosTiposZerados(payload)),
  });
  return toProducao(await res.json());
}

/** DELETE /api/v1/upfs/{upfId}/producao/{id}/ — remove uma atividade produtiva. */
export async function deleteProducao(upfId: string, id: number): Promise<void> {
  await apiClient(`/api/v1/upfs/${upfId}/producao/${id}/`, { method: "DELETE" });
}

// ─── Catálogos ───────────────────────────────────────────────────────────────

async function buscarCatalogo(
  endpoint: string,
  labels: Record<string, string>,
  q: string,
  signal?: AbortSignal,
): Promise<CatalogoItem[]> {
  const qs = new URLSearchParams({ page_size: String(TAMANHO_PAGINA_CATALOGO) });
  if (q.trim()) qs.set("q", q.trim());
  const res = await apiClient(`${endpoint}?${qs}`, { signal });
  const data: Paginated<CatalogoApiItem> = await res.json();
  return data.results.map((item) => toCatalogoItem(item, labels));
}

/** GET /api/v1/catalogos/culturas/?q= — busca no catálogo de culturas. */
export function searchCulturas(
  q: string,
  signal?: AbortSignal,
): Promise<CatalogoItem[]> {
  return buscarCatalogo("/api/v1/catalogos/culturas/", CULTURA_CATEGORIA_LABELS, q, signal);
}

/** GET /api/v1/catalogos/especies-animais/?q= — busca no catálogo de espécies. */
export function searchEspecies(
  q: string,
  signal?: AbortSignal,
): Promise<CatalogoItem[]> {
  return buscarCatalogo(
    "/api/v1/catalogos/especies-animais/",
    ESPECIE_CATEGORIA_LABELS,
    q,
    signal,
  );
}
