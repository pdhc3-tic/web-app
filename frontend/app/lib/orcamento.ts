import { apiClient } from "@/app/lib/api";
import type { NivelSemaforo } from "@/app/lib/semaforo";
import type { Refinar, Schema } from "@/app/lib/apiSchema";

/**
 * Camada de dados do Painel de Orçamento (§5.3.3) sobre o orçamento por pool
 * (#384, #398).
 *
 * O saldo é controlado por pool de rubrica e nível geográfico (nacional,
 * estadual, territorial), sem a Meta. `GET /api/v1/sgp/orcamento/painel/`
 * devolve uma linha por pool no escopo do perfil — a matriz Rubrica × Nível —,
 * com os cinco valores, o semáforo e os limiares PRONTOS do backend. Recalcular
 * aqui criaria uma segunda verdade, e o gestor veria uma cor na tela e outra
 * no e-mail diário.
 *
 * A Meta virou só filtro de relatório: com `?meta=`, cada linha traz também
 * `valor_executado_meta`, o executado do pool nas atividades da Meta, sem
 * mudar o saldo.
 */

// ─── Contrato do endpoint ───────────────────────────────────────────────────

/**
 * Os tipos vêm do schema (#273).
 */

/** Níveis da hierarquia orçamentária — `NivelEnum` do schema. */
export type NivelOrcamento = Schema<"NivelEnum">;

/** Os três que o backend produz. `sem-dado` é decisão da UI (ver nivelDaLinha). */
export type SemaforoOrcamentoApi = Schema<"SemaforoEnum">;

/** `BudgetRubricaNested`. */
export type RubricaApi = Schema<"BudgetRubricaNested">;

/** `EstadoNested`. */
export type EstadoApi = Schema<"EstadoNested">;

/** `TerritorioNested`. */
export type TerritorioApi = Schema<"TerritorioNested">;

/** `LimiaresSemaforo` — `budget_alert_yellow_pct` e `budget_alert_red_pct` do backend. */
export type LimiaresSemaforo = Schema<"LimiaresSemaforo">;

/**
 * Uma linha da matriz Rubrica × Nível — `BudgetPainelLinhaSerializer`.
 *
 * `nivel` é refinado para o tipo enumerado (o schema declara `string`). Os
 * valores decimais são string porque o DRF serializa DecimalField assim.
 */
export type PoolOrcamentoApi = Refinar<
  Schema<"BudgetPainelLinha">,
  { nivel: NivelOrcamento }
>;

/** Filtros de `BudgetPainelQuerySerializer`. Chaves vazias são omitidas. */
export type PainelOrcamentoFiltrosApi = {
  /** Id da Meta: só acrescenta `valor_executado_meta`, não recorta o saldo. */
  meta?: string;
  /** SLUG da rubrica, não id. */
  rubrica?: string;
  /** SIGLA do estado: desce ao estado e aos territórios dele. */
  estado?: string;
  /** Id do território: desce ao pool do território. */
  territorio?: string;
  nivel?: NivelOrcamento;
};

const PAINEL_PATH = "/api/v1/sgp/orcamento/painel/";

/**
 * GET /api/v1/sgp/orcamento/painel/ — os pools do escopo do perfil, já
 * ordenados por rubrica e nível. Sem paginação.
 */
export async function fetchPainelOrcamento(
  filtros: PainelOrcamentoFiltrosApi = {},
  signal?: AbortSignal,
): Promise<PoolOrcamentoApi[]> {
  const qs = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor) qs.set(chave, valor);
  }
  const query = qs.toString();
  const res = await apiClient(query ? `${PAINEL_PATH}?${query}` : PAINEL_PATH, { signal });
  return res.json();
}

/** Os pools de uma rubrica num nível, no escopo do perfil. */
export function fetchPoolsDaRubrica(
  params: { rubrica: string; nivel: NivelOrcamento },
  signal?: AbortSignal,
): Promise<PoolOrcamentoApi[]> {
  return fetchPainelOrcamento({ rubrica: params.rubrica, nivel: params.nivel }, signal);
}

// ─── Movimentações de um pool ───────────────────────────────────────────────

/** `BudgetTransactionTipoEnum`. */
export type TipoTransacao = Schema<"BudgetTransactionTipoEnum">;

/** `BudgetTransaction` — uma linha do ledger, imutável. */
export type TransacaoPoolApi = Schema<"BudgetTransaction">;

export const TIPO_TRANSACAO_LABEL: Record<TipoTransacao, string> = {
  reserva: "Reserva",
  liberacao: "Liberação",
  execucao: "Execução",
  remanejamento: "Remanejamento",
  ajuste: "Ajuste",
  aumento_limite: "Alteração de limite",
};

/** GET /api/v1/sgp/orcamento/pools/{id}/transacoes/ — o histórico, do mais recente ao mais antigo. */
export async function fetchTransacoesDoPool(poolId: number, signal?: AbortSignal): Promise<TransacaoPoolApi[]> {
  const res = await apiClient(`/api/v1/sgp/orcamento/pools/${poolId}/transacoes/`, { signal });
  return res.json();
}

// ─── Catálogo de rubricas ───────────────────────────────────────────────────

/**
 * As 6 rubricas do §5.3.1, na ordem do catálogo — opções do filtro. Constante
 * porque o painel só devolve as que estão no recorte atual: um filtro
 * alimentado pela própria resposta ficaria preso na primeira escolha.
 */
export const RUBRICAS: ReadonlyArray<Pick<RubricaApi, "nome" | "slug">> = [
  { slug: "diarias", nome: "Diárias" },
  { slug: "passagens-aereas", nome: "Passagens Aéreas" },
  { slug: "locacao-veiculo", nome: "Locação de Veículo" },
  { slug: "alimentacao-refeicoes", nome: "Alimentação/Refeições" },
  { slug: "material-grafico", nome: "Material Gráfico" },
  { slug: "equipamentos-capital", nome: "Equipamentos/Capital" },
];

/** Slugs válidos — a página usa para sanear o que vem da URL. */
export const RUBRICA_SLUGS: string[] = RUBRICAS.map((r) => r.slug);

// ─── Semáforo do orçamento ──────────────────────────────────────────────────

/** Só para escrever o número quando não há linha (os limiares vêm em cada pool). */
export const LIMIARES_PADRAO: LimiaresSemaforo = { amarelo: 70, vermelho: 90 };

/** Limiares em vigor para um pool. */
export function limiaresDaLinha(linha: PoolOrcamentoApi | null | undefined): LimiaresSemaforo {
  return linha?.limiares_semaforo ?? LIMIARES_PADRAO;
}

/**
 * Rótulo do semáforo no vocabulário do ORÇAMENTO: o que se mede é quanto do
 * aprovado já foi comprometido, não o ritmo de execução física.
 */
export function labelSemaforoOrcamento(
  nivel: NivelSemaforo,
  { amarelo, vermelho }: LimiaresSemaforo = LIMIARES_PADRAO,
): string {
  switch (nivel) {
    case "verde":
      return `Abaixo de ${amarelo}%`;
    case "amarelo":
      return `${amarelo}–${vermelho - 1}% comprometido`;
    case "vermelho":
      return `Comprometido ≥ ${vermelho}%`;
    case "sem-dado":
      return "Sem orçamento";
  }
}

/** Decimal do DRF ("1234.50") → number. Ausente ou inválido vira 0. */
export function valorNumerico(valor: string | null | undefined): number {
  const n = Number(valor ?? 0);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Nível exibido para um pool: o `semaforo` do backend, exceto sem valor
 * aprovado — sem denominador o backend devolve verde, e a UI diz "Sem orçamento".
 */
export function nivelDaLinha(linha: PoolOrcamentoApi): NivelSemaforo {
  if (valorNumerico(linha.valor_aprovado) <= 0) return "sem-dado";
  return linha.semaforo;
}

/** Percentual comprometido sobre o aprovado. `null` quando não há denominador. */
export function percentualComprometido(linha: PoolOrcamentoApi): number | null {
  const aprovado = valorNumerico(linha.valor_aprovado);
  if (aprovado <= 0) return null;
  return (valorNumerico(linha.valor_comprometido) / aprovado) * 100;
}

/** true quando o pool não tem NENHUM valor lançado. */
export function linhaVazia(linha: PoolOrcamentoApi): boolean {
  return (
    valorNumerico(linha.valor_aprovado) === 0 &&
    valorNumerico(linha.valor_distribuido) === 0 &&
    valorNumerico(linha.valor_comprometido) === 0 &&
    valorNumerico(linha.valor_executado) === 0
  );
}

// ─── Rótulos ────────────────────────────────────────────────────────────────

const NIVEL_LABEL: Record<NivelOrcamento, string> = {
  nacional: "Nacional",
  estadual: "Estadual",
  territorial: "Territorial",
};

export function nivelOrcamentoLabel(nivel: NivelOrcamento): string {
  return NIVEL_LABEL[nivel];
}

/** O local de um pool: "Nacional", o nome do estado ou o do território. */
export function nomeDoPool(pool: Pick<PoolOrcamentoApi, "nivel" | "estado" | "territorio">): string {
  if (pool.nivel === "nacional") return "Nacional";
  if (pool.nivel === "estadual") return pool.estado?.nome ?? "Estado";
  return pool.territorio?.nome ?? "Território";
}

// ─── Escrita: distribuição orçamentária (§5.3.2) ────────────────────────────

/**
 * Payload de `POST /sgp/orcamento/pools/` — `BudgetPoolCreateRequest`.
 *
 * `nivel` é refinado para excluir `"nacional"` (esta tela não cria pools
 * nacionais) e `reserva_ugp` é tornado opcional (omitido = false).
 */
export type CriarPoolPayload = Refinar<
  Schema<"BudgetPoolCreateRequest">,
  { nivel: Exclude<NivelOrcamento, "nacional">; reserva_ugp?: boolean }
>;

/**
 * POST /api/v1/sgp/orcamento/pools/ — o service confere o teto do pool de cima
 * dentro de uma transação; o erro chega em `valor_alocado`.
 */
export async function criarPool(payload: CriarPoolPayload): Promise<PoolOrcamentoApi> {
  const res = await apiClient("/api/v1/sgp/orcamento/pools/", { method: "POST", body: JSON.stringify(payload) });
  return res.json();
}

/**
 * POST /api/v1/sgp/orcamento/pools/ no nível nacional (#438) — a dotação de uma
 * rubrica, o topo da hierarquia. Não tem pai, então o service não confere teto;
 * só UGP e Super Admin passam por `_autorizar`. O banco aceita um único pool
 * nacional por rubrica: o segundo POST volta 400 em `nivel`, e quem já tem pool
 * ajusta com `atualizarPool`.
 *
 * Ainda não há TED contra o que validar (#437); quando houver, o teto do valor
 * aprovado na versão vigente chega como erro em `valor_alocado`.
 */
export async function lancarDotacaoNacional(rubricaId: number, valorAlocado: string): Promise<PoolOrcamentoApi> {
  const res = await apiClient("/api/v1/sgp/orcamento/pools/", {
    method: "POST",
    body: JSON.stringify({ rubrica_id: rubricaId, nivel: "nacional", valor_alocado: valorAlocado }),
  });
  return res.json();
}

/**
 * O menor valor que a dotação de um pool aceita, como `atualizar_valor_alocado`
 * do backend: o que já desceu ao nível de baixo mais o que já foi comprometido e
 * executado nele.
 */
export function pisoDoPool(pool: Pick<PoolOrcamentoApi, "valor_distribuido" | "valor_comprometido" | "valor_executado">): number {
  return (
    valorNumerico(pool.valor_distribuido) +
    valorNumerico(pool.valor_comprometido) +
    valorNumerico(pool.valor_executado)
  );
}

/**
 * PATCH /api/v1/sgp/orcamento/pools/{id}/ — só o valor muda. Reduzir abaixo do
 * já comprometido e executado (ou do distribuído aos filhos) é recusado.
 */
export async function atualizarPool(poolId: number, valorAlocado: string): Promise<PoolOrcamentoApi> {
  const res = await apiClient(`/api/v1/sgp/orcamento/pools/${poolId}/`, {
    method: "PATCH",
    body: JSON.stringify({ valor_alocado: valorAlocado }),
  });
  return res.json();
}

// ─── Saldo por rubrica no território (Issue #232) ───────────────────────────

/** Espelha `BLOQUEIO_SALDO_ZERO` do backend: o painel não devolve `motivo_bloqueio`. */
export const BLOQUEIO_SALDO_ZERO = "Bloqueado para novas solicitações quando saldo da rubrica é zero.";

/** Uma rubrica com o saldo do território do usuário, pronta para exibição. */
export type SaldoRubrica = {
  rubrica: RubricaApi;
  /** Decimal como string, direto do backend. */
  saldo: string;
  /** Valor numérico — usado só para comparar com zero, nunca para exibir. */
  saldoNumero: number;
  /** Saldo zerado ou negativo: não cabe nova solicitação. */
  bloqueada: boolean;
  /** Remanejamento pode deixar o saldo abaixo de zero; a UI destaca, não esconde. */
  negativa: boolean;
};

/**
 * O saldo de cada rubrica do catálogo nos pools territoriais do escopo do
 * usuário (o ADT vê só o do próprio território). Sem Meta desde a #384: o
 * saldo é do pool.
 *
 * O painel só devolve os pools que existem; uma rubrica sem pool no território
 * não tem saldo nenhum, e o card a mostra bloqueada em vez de omiti-la. Com
 * mais de um território, o saldo da rubrica é a soma dos pools dela.
 *
 * Para um ADT sem território o backend responde 403 `SEM_TERRITORIO`.
 */
export async function fetchSaldoPorRubrica(signal?: AbortSignal): Promise<SaldoRubrica[]> {
  const pools = await fetchPainelOrcamento({ nivel: "territorial" }, signal);
  return RUBRICAS.map((r) => {
    const daRubrica = pools.filter((p) => p.rubrica.slug === r.slug);
    const numero = daRubrica.reduce((soma, p) => soma + valorNumerico(p.saldo_disponivel), 0);
    return {
      rubrica: daRubrica[0]?.rubrica ?? { id: 0, ...r },
      saldo: daRubrica.length === 1 ? daRubrica[0].saldo_disponivel : numero.toFixed(2),
      saldoNumero: numero,
      bloqueada: numero <= 0,
      negativa: numero < 0,
    };
  });
}
