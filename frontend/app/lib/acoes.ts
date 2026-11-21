import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { Refinar, Schema } from "@/app/lib/apiSchema";

// ─── Constantes ─────────────────────────────────────────────────────────────

/**
 * Formato do número da Ação: X.Y.Z (1.1.1, 2.3.4), com X.Y igual ao número
 * da Submeta. Validar aqui só antecipa a resposta; quem manda é o servidor,
 * que também checa a unicidade dentro da Submeta.
 */
export const NUMERO_ACAO_RE = /^\d+\.\d+\.\d+$/;

// ─── Status de execução ─────────────────────────────────────────────────────

/** Valores de WorkPlanAcao.status_execucao. */
export type AcaoStatus = "no_prazo" | "em_atraso" | "concluida";

// O rótulo de cada situação vem de `useRotuloChoice("status_plano_trabalho")` (#272).

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** `WorkPlanAcaoListSerializer`. */
export type Acao = Refinar<
  Schema<"WorkPlanAcaoList">,
  { status_execucao: AcaoStatus }
>;

/** Campos graváveis (POST/PATCH) — `WorkPlanAcaoRequest` do schema. */
export type AcaoWritePayload = Schema<"WorkPlanAcaoRequest">;

// ─── Progresso ──────────────────────────────────────────────────────────────

export type Progresso = {
  /** Atividades concluídas vinculadas à Ação. */
  realizada: number;
  /** Quantidade planejada na unidade da Ação. */
  planejada: number;
  /** 0–100, já limitado. `null` quando não há planejamento para comparar. */
  percentual: number | null;
};

/**
 * Progresso de uma Ação.
 *
 * ATENÇÃO à semântica do backend: `quantidade_realizada` é a CONTAGEM de
 * Atividades concluídas, não a soma de quantidades entregues. Para Ações cuja
 * unidade é um evento (oficina, seminário, intercâmbio) isso equivale ao
 * esperado — uma Atividade é uma unidade. Para unidades de quantidade
 * ("família atendida", "unidade implementada") o número subestima, porque uma
 * única Atividade pode ter entregue várias unidades e não há onde registrar
 * isso. A UI exibe o que o backend calcula; corrigir a conta aqui inventaria um
 * número que não existe no domínio.
 *
 * Planejada zero devolve `percentual: null` — sem denominador não há progresso,
 * e 0/0 não é 0%.
 *
 * Aceita qualquer objeto com as duas quantidades, e não só uma `Acao`: o Painel
 * de Acompanhamento passa a Ação que vem do endpoint do painel, que carrega os
 * mesmos dois campos sem ser o serializer completo.
 */
export function progressoAcao(
  acao: Pick<Acao, "quantidade_realizada" | "quantidade_planejada">,
): Progresso {
  const realizada = Number(acao.quantidade_realizada) || 0;
  const planejada = Number(acao.quantidade_planejada) || 0;
  if (planejada <= 0) return { realizada, planejada, percentual: null };
  const bruto = (realizada / planejada) * 100;
  return {
    realizada,
    planejada,
    percentual: Math.min(100, Math.max(0, bruto)),
  };
}

/** "2 de 12 intercâmbios" — o número legível quando a barra é fina demais. */
export function progressoLabel(
  acao: Pick<Acao, "quantidade_realizada" | "quantidade_planejada">,
): string {
  const { realizada, planejada } = progressoAcao(acao);
  return `${formatQtd(realizada)} de ${formatQtd(planejada)}`;
}

/** Decimais do DRF vêm como "12.00"; exibir sem casas quando forem inteiros. */
export function formatQtd(value: number | string | null | undefined): string {
  const n = Number(value) || 0;
  return Number.isInteger(n)
    ? String(n)
    : n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

// ─── API ────────────────────────────────────────────────────────────────────

const BASE_PATH = "/api/v1/acoes/";

/**
 * GET /api/v1/acoes/?meta={id}
 *
 * O detalhe da Meta já devolve `acoes[]` completo, então a tela não precisa
 * desta chamada no carregamento. Fica disponível para quem só quer as Ações.
 */
export async function listAcoes(
  metaId: number,
  signal?: AbortSignal,
): Promise<Acao[]> {
  const res = await apiClient(
    `${BASE_PATH}?meta=${metaId}&page_size=100&ordering=numero`,
    { signal },
  );
  const data: Paginated<Acao> = await res.json();
  return data.results;
}

/** POST /api/v1/acoes/ — restrito a UGP/Super Admin no backend. */
export async function createAcao(payload: AcaoWritePayload): Promise<Acao> {
  const res = await apiClient(BASE_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /api/v1/acoes/{id}/ — restrito a UGP/Super Admin no backend. */
export async function updateAcao(
  id: number,
  payload: AcaoWritePayload,
): Promise<Acao> {
  const res = await apiClient(`${BASE_PATH}${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/**
 * DELETE /api/v1/acoes/{id}/
 *
 * O backend responde 400 com `{detail: "..."}` quando há Atividades de Campo
 * vinculadas (a FK Activity.acao é PROTECT); o apiClient converte isso em
 * ApiError com a mensagem pronta para exibição.
 */
export async function deleteAcao(id: number): Promise<void> {
  await apiClient(`${BASE_PATH}${id}/`, { method: "DELETE" });
}

// ─── Submeta e Indicador (seletores do formulário) ──────────────────────────

export type SubmetaOption = Schema<"WorkPlanSubmeta">;
export type IndicadorOption = Schema<"Indicator">;

/** Tamanho de página pedido: o teto de `UFPAPagination` (`max_page_size = 200`). */
const SUBMETAS_POR_PAGINA = 200;

/**
 * GET /api/v1/sgp/submetas/?meta={metaId} — TODAS as Submetas da Meta.
 *
 * A rota é paginada e a Meta não tem limite de Submetas: a função segue as
 * páginas até o fim (revisão do PR #434). Ler só a primeira deixava de fora as
 * seguintes, inclusive uma recém-criada, da lista, do seletor da Ação e da
 * sugestão do próximo número. Um registro repetido entre páginas entra uma vez.
 */
export async function listSubmetasDaMeta(
  metaId: number,
  signal?: AbortSignal,
): Promise<SubmetaOption[]> {
  const porId = new Map<number, SubmetaOption>();
  for (let page = 1; ; page++) {
    const qs = new URLSearchParams({ meta: String(metaId), page: String(page), page_size: String(SUBMETAS_POR_PAGINA) });
    const res = await apiClient(`/api/v1/sgp/submetas/?${qs}`, { signal });
    const data: Paginated<SubmetaOption> = await res.json();
    for (const s of data.results) porId.set(s.id, s);
    if (!data.next || data.results.length === 0) break;
  }
  return Array.from(porId.values());
}

/** GET /api/v1/sgp/indicadores/?ativo=true — catálogo de indicadores ativos. */
export async function listIndicadores(
  signal?: AbortSignal,
): Promise<IndicadorOption[]> {
  const res = await apiClient(
    `/api/v1/sgp/indicadores/?ativo=true&page_size=200`,
    { signal },
  );
  const data: Paginated<IndicadorOption> = await res.json();
  return data.results;
}
