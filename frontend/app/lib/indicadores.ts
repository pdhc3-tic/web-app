import { apiClient } from "@/app/lib/api";
import type { Refinar, Schema } from "@/app/lib/apiSchema";
import type { Paginated } from "@/app/lib/users";

/**
 * Catálogo institucional de Indicadores (SGP §5.4, #453).
 *
 * `/api/v1/sgp/indicadores/`: leitura para quem lê o Plano de Trabalho, escrita
 * de UGP e Super Admin. Os dois bloqueios da DRS são do backend e chegam como
 * 409 com `code`:
 * - `indicador_em_uso`: excluir um Indicador com Ações (só inativar);
 * - `confirmacao_necessaria`: trocar a forma de apuração de um Indicador com
 *   Ações, que recalcula as quantidades — o reenvio leva `confirmar_recalculo`.
 */

export type UnidadeMedida = Schema<"UnidadeMedidaEnum">;
export type FormaApuracao = Schema<"FormaApuracaoEnum">;
export type CategoriaIndicador = Schema<"IndicatorCategoriaEnum">;
/** `DESAGREGACAO_CHOICES`: o schema descreve o campo como JSON livre. */
export type Desagregacao = "genero" | "geracao" | "pct" | "territorio";

/** `IndicatorSerializer`. `ods_ids` e `desagregacoes` são `JSONField` sem forma no schema. */
export type Indicador = Refinar<
  Schema<"Indicator">,
  { categoria: CategoriaIndicador | ""; ods_ids: number[]; desagregacoes: Desagregacao[]; ativo: boolean }
>;

export const CODIGO_EM_USO = "indicador_em_uso";
export const CODIGO_CONFIRMAR_RECALCULO = "confirmacao_necessaria";

// Os rótulos não estão em `/api/v1/choices/` (pendencias-backend-sprint-12g.md,
// item 2): são cópia das choices de `apps/sgp/models/indicator.py`. O `Record`
// pelo enum do schema faz o tsc apontar um valor novo quando os tipos forem
// regenerados.

export const UNIDADE_MEDIDA_LABEL: Record<UnidadeMedida, string> = {
  unidade: "Unidade",
  familia: "Família",
  pessoa: "Pessoa",
  evento: "Evento",
  plano: "Plano",
  relatorio: "Relatório",
  hectare: "Hectare",
  outro: "Outro",
};

export const FORMA_APURACAO_LABEL: Record<FormaApuracao, string> = {
  contagem_atividades: "Contagem de atividades concluídas",
  soma_ufpas: "Soma de UFPAs vinculadas",
  soma_participantes: "Soma de participantes",
  manual: "Lançamento manual pela UGP",
};

export const CATEGORIA_LABEL: Record<CategoriaIndicador, string> = {
  formacao: "Formação",
  assistencia_tecnica: "Assistência técnica",
  estruturacao_produtiva: "Estruturação produtiva",
  gestao: "Gestão",
  outro: "Outro",
};

export const DESAGREGACAO_LABEL: Record<Desagregacao, string> = {
  genero: "Gênero",
  geracao: "Geração",
  pct: "PCT",
  territorio: "Território",
};

export function opcoes<T extends string>(rotulos: Record<T, string>): { value: T; label: string }[] {
  return (Object.keys(rotulos) as T[]).map((value) => ({ value, label: rotulos[value] }));
}

/** O rótulo, ou o próprio código quando o backend mandar um valor que o front não conhece. */
export function rotulo<T extends string>(rotulos: Record<T, string>, valor: string | null | undefined): string {
  if (!valor) return "";
  return (rotulos as Record<string, string>)[valor] ?? valor;
}

export type FiltrosIndicadores = {
  q: string;
  /** "ativos" (padrão), "inativos" ou "todos". */
  situacao: "ativos" | "inativos" | "todos";
  categoria: string;
  forma_apuracao: string;
};

export const FILTROS_PADRAO: FiltrosIndicadores = { q: "", situacao: "ativos", categoria: "", forma_apuracao: "" };

/** GET /api/v1/sgp/indicadores/ — uma página, com os filtros do catálogo. */
export async function listarIndicadores(
  filtros: FiltrosIndicadores,
  pagina: { offset: number; limit: number },
  signal?: AbortSignal,
): Promise<Paginated<Indicador>> {
  const qs = new URLSearchParams({
    page: String(Math.floor(pagina.offset / pagina.limit) + 1),
    page_size: String(pagina.limit),
  });
  if (filtros.q.trim()) qs.set("q", filtros.q.trim());
  if (filtros.situacao !== "todos") qs.set("ativo", filtros.situacao === "ativos" ? "true" : "false");
  if (filtros.categoria) qs.set("categoria", filtros.categoria);
  if (filtros.forma_apuracao) qs.set("forma_apuracao", filtros.forma_apuracao);
  const res = await apiClient(`/api/v1/sgp/indicadores/?${qs}`, { signal });
  return res.json();
}

export type IndicadorPayload = {
  codigo: string;
  nome: string;
  unidade_medida: UnidadeMedida;
  forma_apuracao: FormaApuracao;
  categoria: CategoriaIndicador | "";
  ods_ids: number[];
  desagregacoes: Desagregacao[];
  ativo: boolean;
};

/** POST /api/v1/sgp/indicadores/ */
export async function criarIndicador(payload: IndicadorPayload): Promise<Indicador> {
  const res = await apiClient("/api/v1/sgp/indicadores/", { method: "POST", body: JSON.stringify(payload) });
  return res.json();
}

/**
 * PATCH /api/v1/sgp/indicadores/{id}/ — `confirmarRecalculo` só depois do 409
 * `confirmacao_necessaria`, quando o usuário aceitou recalcular as Ações.
 */
export async function atualizarIndicador(
  id: number,
  payload: Partial<IndicadorPayload>,
  confirmarRecalculo = false,
): Promise<Indicador> {
  const corpo = confirmarRecalculo ? { ...payload, confirmar_recalculo: true } : payload;
  const res = await apiClient(`/api/v1/sgp/indicadores/${id}/`, { method: "PATCH", body: JSON.stringify(corpo) });
  return res.json();
}

/** DELETE /api/v1/sgp/indicadores/{id}/ — 409 `indicador_em_uso` com Ações vinculadas. */
export async function excluirIndicador(id: number): Promise<void> {
  await apiClient(`/api/v1/sgp/indicadores/${id}/`, { method: "DELETE" });
}
