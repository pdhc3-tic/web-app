import { ApiError, apiClient } from "./api";

/**
 * Limites de gasto (#400, backend #385 / PR #411).
 *
 * Duas camadas, no mesmo `SpendingLimit`:
 * - **padrão por perfil** (`escopo: "perfil"`): o valor que cada pessoa de um
 *   perfil operacional recebe numa rubrica. Vale até ser alterado;
 * - **linha individual** (`escopo: "individual"`): a de uma pessoa num período.
 *   Nasce do padrão na primeira reserva (`herdado: true`) ou é uma
 *   **sobrescrita** criada pela UGP, com justificativa (`herdado: false`).
 *
 * Quem decide período, precedência e teto é o backend
 * (`apps/sgp/budget/limites.py`). A tela lê o que ele gravou.
 */

const BASE = "/api/v1/sgp/orcamento/limites/";

export type EscopoLimite = "perfil" | "individual";

/** `SpendingLimitSerializer`. Decimais como string, datas `YYYY-MM-DD`. */
export type LimiteGasto = {
  id: number;
  escopo: EscopoLimite;
  perfil: number | null;
  perfil_slug: string | null;
  user: number | null;
  user_nome: string | null;
  rubrica: number;
  rubrica_slug: string;
  rubrica_nome: string;
  territorio: number | null;
  valor_limite: string;
  valor_comprometido: string;
  valor_executado: string;
  saldo_disponivel: string;
  /** Linha individual que nasceu do padrão do perfil; `false` = sobrescrita. */
  herdado: boolean;
  justificativa: string;
  periodo_inicio: string;
  periodo_fim: string;
  criado_em: string;
  atualizado_em: string;
};

/** Os perfis que recebem limite: `PERFIS_OPERACIONAIS` do backend. */
export const PERFIS_OPERACIONAIS = ["adt-acr", "articulador-estadual"] as const;

export type PerfilOperacional = { id: number; slug: string; nome: string };

/** GET .../limites/?escopo=&data= — os vigentes na data (sem paginação). */
export async function listLimites(
  params: { escopo: EscopoLimite; data: string },
  signal?: AbortSignal,
): Promise<LimiteGasto[]> {
  const qs = new URLSearchParams({ escopo: params.escopo, data: params.data });
  const res = await apiClient(`${BASE}?${qs}`, { signal });
  return res.json();
}

export type NovoLimitePayload =
  | { escopo: "perfil"; perfil: number; rubrica: number; valor_limite: string; justificativa: string }
  | { escopo: "individual"; user: number; rubrica: number; valor_limite: string; justificativa: string };

/**
 * POST .../limites/ — sem período, vale o vigente (o backend calcula). O
 * padrão do perfil não tem fim; a sobrescrita exige justificativa. Uma
 * sobrescrita sobre a linha herdada do mesmo período a converte, em vez de
 * abrir outra.
 */
export async function criarLimite(payload: NovoLimitePayload): Promise<LimiteGasto> {
  const res = await apiClient(BASE, { method: "POST", body: JSON.stringify(payload) });
  return res.json();
}

/**
 * PATCH .../limites/{id}/ — só valor e justificativa (obrigatória quando o
 * valor muda). Num padrão já em uso, o backend agenda o valor novo para o
 * período seguinte e devolve a linha nova: `periodo_inicio` no futuro.
 */
export async function alterarLimite(
  id: number,
  payload: { valor_limite: string; justificativa: string },
): Promise<LimiteGasto> {
  const res = await apiClient(`${BASE}${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
  return res.json();
}

/** GET /api/v1/roles/ filtrado pelos perfis operacionais, na ordem de `PERFIS_OPERACIONAIS`. */
export async function fetchPerfisOperacionais(signal?: AbortSignal): Promise<PerfilOperacional[]> {
  const res = await apiClient("/api/v1/roles/?limit=200&ativo=true", { signal });
  const data: { results: PerfilOperacional[] } = await res.json();
  return PERFIS_OPERACIONAIS.flatMap((slug) => {
    const r = data.results.find((p) => p.slug === slug);
    return r ? [{ id: r.id, slug: r.slug, nome: r.nome }] : [];
  });
}

// ─── Período ────────────────────────────────────────────────────────────────

/** Valores de `budget_limit_period`. */
export type Periodicidade = "mensal" | "trimestral" | "semestral" | "vigencia";

const MESES: Record<Exclude<Periodicidade, "vigencia">, number> = {
  mensal: 1,
  trimestral: 3,
  semestral: 6,
};

/** O padrão do backend (`PERIODO_PADRAO`) quando o parâmetro tem valor desconhecido. */
const PERIODICIDADE_PADRAO: Periodicidade = "trimestral";

/** GET /api/v1/system-config/budget_limit_period/ — leitura liberada à UGP. */
export async function fetchPeriodicidade(signal?: AbortSignal): Promise<Periodicidade> {
  const res = await apiClient("/api/v1/system-config/budget_limit_period/", { signal });
  const data: { valor: string } = await res.json();
  return paraPeriodicidade(data.valor);
}

export function paraPeriodicidade(valor: string | null | undefined): Periodicidade {
  const v = (valor ?? "").trim().toLowerCase();
  return v === "mensal" || v === "trimestral" || v === "semestral" || v === "vigencia"
    ? v
    : PERIODICIDADE_PADRAO;
}

export type Periodo = { inicio: string; fim: string; rotulo: string };

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (ano: number, mes: number, dia: number) => `${ano}-${pad(mes)}-${pad(dia)}`;
const MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/**
 * Início, fim e rótulo do período que contém `data` (`YYYY-MM-DD`).
 *
 * Espelha `periodo_de` de `apps/sgp/budget/limites.py`: blocos de 1, 3 ou 6
 * meses contados de janeiro; na vigência, um período único. O backend não
 * devolve as datas do período na listagem (pendencias-backend-sprint-12b.md,
 * item 1); o cálculo serve só para navegar e rotular — quem filtra é o
 * `?data=`.
 */
export function periodoDe(data: string, periodicidade: Periodicidade): Periodo {
  if (periodicidade === "vigencia") {
    return { inicio: "2000-01-01", fim: "2099-12-31", rotulo: "Vigência do TED" };
  }
  const [ano, mes] = data.split("-").map(Number);
  const meses = MESES[periodicidade];
  const mesInicial = Math.floor((mes - 1) / meses) * meses + 1;
  const mesFinal = mesInicial + meses - 1;
  const ultimoDia = new Date(ano, mesFinal, 0).getDate();
  const ordem = Math.floor((mes - 1) / meses) + 1;
  const rotulo =
    periodicidade === "mensal"
      ? `${MESES_ABREV[mesInicial - 1]}/${ano}`
      : `${ordem}º ${periodicidade === "trimestral" ? "trimestre" : "semestre"} de ${ano}`;
  return { inicio: iso(ano, mesInicial, 1), fim: iso(ano, mesFinal, ultimoDia), rotulo };
}

/** Uma data dentro do período anterior (`passo = -1`) ou seguinte (`passo = 1`). */
export function dataVizinha(periodo: Periodo, passo: -1 | 1): string {
  const [ano, mes, dia] = (passo < 0 ? periodo.inicio : periodo.fim).split("-").map(Number);
  const d = new Date(ano, mes - 1, dia + passo);
  return iso(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

/** Hoje em `YYYY-MM-DD`, no fuso do navegador (o backend usa o local do servidor). */
export function hojeIso(agora: Date = new Date()): string {
  return iso(agora.getFullYear(), agora.getMonth() + 1, agora.getDate());
}

// ─── Precedência e erros ────────────────────────────────────────────────────

export type Precedencia = "padrao" | "herdado" | "sobrescrito";

export const PRECEDENCIA_LABEL: Record<Precedencia, string> = {
  padrao: "Padrão do perfil",
  herdado: "Herdado do perfil",
  sobrescrito: "Sobrescrito",
};

/** Qual regra define o valor da linha, como o backend gravou. */
export function precedenciaDo(limite: Pick<LimiteGasto, "escopo" | "herdado">): Precedencia {
  if (limite.escopo === "perfil") return "padrao";
  return limite.herdado ? "herdado" : "sobrescrito";
}

export type Sobrealocacao = { somaLimites: string; valorPool: string; mensagem: string };

const texto = (v: unknown): string | null =>
  typeof v === "string" ? v : Array.isArray(v) && typeof v[0] === "string" ? v[0] : null;

/**
 * O 400 de `exigir_dentro_do_pool`: com a sobrealocação desligada, a soma dos
 * limites do território não pode passar do pool. O corpo traz
 * `{valor_limite, soma_limites, valor_pool, territorio}`; qualquer outro erro
 * devolve `null`.
 */
export function sobrealocacaoDoErro(err: unknown): Sobrealocacao | null {
  if (!(err instanceof ApiError) || !err.raw || typeof err.raw !== "object") return null;
  const raw = err.raw as Record<string, unknown>;
  const somaLimites = texto(raw.soma_limites);
  const valorPool = texto(raw.valor_pool);
  if (somaLimites === null || valorPool === null) return null;
  return { somaLimites, valorPool, mensagem: texto(raw.valor_limite) ?? err.message };
}
