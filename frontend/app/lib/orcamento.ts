import { apiClient } from "@/app/lib/api";
import type { NivelSemaforo } from "@/app/lib/semaforo";

/**
 * Camada de dados do Painel de Orçamento (§5.3.3).
 *
 * Os cinco valores, o semáforo e o alerta de 80% vêm PRONTOS do backend, por
 * `GET /api/v1/sgp/orcamento/painel/` (Issue #224). A regra de classificação
 * mora em `apps/sgp/services/budget.py::_semaforo_orcamento` e é a mesma que
 * alimenta a task diária `check_budget_threshold_alert` — recalcular aqui
 * criaria uma segunda verdade, e o gestor veria uma cor na tela e outra no
 * e-mail. Mesmo princípio já adotado em `semaforo.ts` para o PT físico.
 *
 * ─── O que "nível" significa nesta tela ─────────────────────────────────────
 *
 * O endpoint devolve UM nível por vez (nacional, estadual ou territorial),
 * resolvido pelo perfil do usuário. `estado` e `territorio` não recortam um
 * subconjunto das mesmas linhas: eles DESCEM a hierarquia, e as linhas passam a
 * representar outro nível. É por isso que a tela nomeia o nível exibido em vez
 * de tratar esses dois campos como filtros comuns.
 */

// ─── Contrato do endpoint ───────────────────────────────────────────────────

/** Níveis da hierarquia orçamentária — espelha `BudgetAllocation.Nivel`. */
export type NivelOrcamento = "nacional" | "estadual" | "territorial";

/** Os três que o backend produz. `sem-dado` é decisão da UI (ver nivelDaLinha). */
export type SemaforoOrcamentoApi = "verde" | "amarelo" | "vermelho";

export type MetaOrcamentoApi = {
  id: number;
  numero: number;
  titulo: string;
};

export type RubricaApi = {
  id: number;
  nome: string;
  slug: string;
};

export type EstadoApi = {
  id: number;
  sigla: string;
  nome: string;
};

export type TerritorioApi = {
  id: number;
  nome: string;
};

/**
 * Uma célula da matriz Meta × Rubrica — espelha `BudgetPainelLinhaSerializer`.
 *
 * Os valores são string porque o DRF serializa DecimalField assim, como no
 * resto da API. `formatCurrencyBRL` aceita string direto; converter para number
 * antes da hora só perderia precisão sem ganhar nada.
 */
export type PainelOrcamentoLinhaApi = {
  meta: MetaOrcamentoApi;
  rubrica: RubricaApi;
  nivel: NivelOrcamento;
  valor_aprovado: string;
  valor_distribuido: string;
  valor_comprometido: string;
  valor_executado: string;
  saldo_disponivel: string;
  semaforo: SemaforoOrcamentoApi;
  /** true no mesmo limiar de `vermelho` — ≥ 80% do aprovado comprometido. */
  alerta_80: boolean;
};

/** Filtros de `BudgetPainelQuerySerializer`. */
export type PainelOrcamentoFiltrosApi = {
  /** Id da Meta. */
  meta?: string;
  /** SLUG da rubrica, não id. */
  rubrica?: string;
  /** SIGLA do estado, não id. */
  estado?: string;
  /** Id do território. */
  territorio?: string;
};

const PAINEL_PATH = "/api/v1/sgp/orcamento/painel/";

/**
 * GET /api/v1/sgp/orcamento/painel/
 *
 * Sem paginação: devolve a matriz inteira (Metas × rubricas ativas) já no nível
 * que o perfil do usuário permite. Chaves vazias são omitidas — o backend valida
 * cada uma contra a FK real e responderia 400 a uma string vazia.
 */
export async function fetchPainelOrcamento(
  filtros: PainelOrcamentoFiltrosApi = {},
  signal?: AbortSignal,
): Promise<PainelOrcamentoLinhaApi[]> {
  const qs = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor) qs.set(chave, valor);
  }
  const query = qs.toString();

  const res = await apiClient(query ? `${PAINEL_PATH}?${query}` : PAINEL_PATH, {
    signal,
  });
  return res.json();
}

// ─── Detalhamento por nível (drill-down) ────────────────────────────────────

/** Uma alocação concreta — espelha `BudgetAllocationSerializer`. */
export type AlocacaoApi = {
  id: number;
  meta: number;
  rubrica: RubricaApi;
  nivel: NivelOrcamento;
  estado: EstadoApi | null;
  territorio: TerritorioApi | null;
  valor_alocado: string;
  valor_comprometido: string;
  valor_executado: string;
  reserva_ugp: boolean;
  saldo_disponivel: string;
  criado_por: number | null;
  criado_em: string;
};

/**
 * Uma rubrica em `GET /api/v1/sgp/metas/{id}/orcamento/` — espelha
 * `BudgetRubricaOrcamentoSerializer`.
 *
 * Atenção à assimetria de escopo, que é do backend: os cinco valores agregados
 * são SEMPRE do nível nacional e vêm para qualquer perfil (§B2 — nacional não é
 * dado sensível por território), enquanto `detalhamento` já vem recortado por
 * `orcamento_detalhamento_scope` e nunca inclui linhas nacionais.
 */
export type RubricaOrcamentoApi = {
  rubrica: RubricaApi;
  valor_aprovado: string;
  valor_distribuido: string;
  valor_comprometido: string;
  valor_executado: string;
  saldo_disponivel: string;
  detalhamento: AlocacaoApi[];
};

/**
 * GET /api/v1/sgp/metas/{id}/orcamento/ — alimenta o SlideOver de drill-down.
 *
 * Devolve todas as rubricas ativas da Meta; a tela usa só a da célula clicada.
 * Buscar a Meta inteira e filtrar no cliente evita um endpoint por rubrica, e a
 * resposta é pequena (6 rubricas).
 */
export async function fetchOrcamentoDaMeta(
  metaId: number,
  signal?: AbortSignal,
): Promise<RubricaOrcamentoApi[]> {
  const res = await apiClient(`/api/v1/sgp/metas/${metaId}/orcamento/`, {
    signal,
  });
  return res.json();
}

// ─── Catálogo de rubricas ───────────────────────────────────────────────────

/**
 * As 6 rubricas do §5.3.1, na ordem do catálogo.
 *
 * Espelha a migration `0017_seed_rubricas` do backend, que é a única fonte
 * delas — não há endpoint público de rubricas, e o painel só devolve as que
 * aparecem no recorte atual (filtrar por uma rubrica reduz a resposta a ela, e
 * um filtro alimentado pela própria resposta ficaria preso na primeira escolha).
 *
 * Constante, e não estado derivado, pelo mesmo motivo que `SITUACOES_VALIDAS`
 * do PainelFilters é constante: é um catálogo fechado do domínio, versionado
 * junto com o schema. Se a UGP desativar uma rubrica, o filtro ainda a
 * ofereceria e o resultado viria vazio — mesmo risco já aceito lá, e o preço de
 * evitá-lo seria uma segunda requisição do painel a cada abertura da tela.
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

/**
 * Limiar de vermelho e do alerta: 80% do aprovado já comprometido. Espelha
 * `LIMIAR_SEMAFORO_VERMELHO` do backend — aqui serve só para escrever o número
 * no texto do alerta, não para classificar.
 */
export const LIMIAR_ALERTA_PCT = 80;

/** Limiar de amarelo — `LIMIAR_SEMAFORO_AMARELO` do backend. */
export const LIMIAR_ATENCAO_PCT = 60;

const LABEL_ORCAMENTO: Record<NivelSemaforo, string> = {
  verde: `Abaixo de ${LIMIAR_ATENCAO_PCT}%`,
  amarelo: `${LIMIAR_ATENCAO_PCT}–${LIMIAR_ALERTA_PCT - 1}% comprometido`,
  vermelho: `Comprometido ≥ ${LIMIAR_ALERTA_PCT}%`,
  "sem-dado": "Sem orçamento",
};

/**
 * Rótulo do semáforo no vocabulário do ORÇAMENTO.
 *
 * `nivelLabel` de semaforo.ts diz "No ritmo / Atenção / Crítica", que fala de
 * execução FÍSICA das Ações do PT — dizer que uma rubrica está "no ritmo"
 * quando o que se mede é quanto do aprovado já foi comprometido seria uma
 * afirmação diferente da que o dado sustenta. As CORES são as mesmas (tokens do
 * B7, via SemaforoBadge); só o texto muda, pela prop `label`.
 */
export function labelSemaforoOrcamento(nivel: NivelSemaforo): string {
  return LABEL_ORCAMENTO[nivel];
}

/** Decimal do DRF ("1234.50") → number. Ausente ou inválido vira 0. */
export function valorNumerico(valor: string | null | undefined): number {
  const n = Number(valor ?? 0);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Nível exibido para uma linha da matriz.
 *
 * É o `semaforo` do backend, com uma única ressalva: sem valor aprovado não há
 * denominador, e o backend classifica esse caso como VERDE porque o percentual
 * fica em 0. Deixar passar pintaria de "saudável" uma combinação Meta/Rubrica
 * que simplesmente não tem orçamento — a UI a exibe como "Sem orçamento".
 *
 * É exatamente a mesma correção que `semaforo.ts::nivelDaApi` faz para Ações
 * sem `quantidade_planejada`; o precedente é dele.
 */
export function nivelDaLinha(linha: PainelOrcamentoLinhaApi): NivelSemaforo {
  if (valorNumerico(linha.valor_aprovado) <= 0) return "sem-dado";
  return linha.semaforo;
}

/** Percentual comprometido sobre o aprovado. `null` quando não há denominador. */
export function percentualComprometido(
  linha: PainelOrcamentoLinhaApi,
): number | null {
  const aprovado = valorNumerico(linha.valor_aprovado);
  if (aprovado <= 0) return null;
  return (valorNumerico(linha.valor_comprometido) / aprovado) * 100;
}

/**
 * true quando a linha não tem NENHUM valor lançado.
 *
 * Existe porque `painel_orcamento` emite uma linha para cada par Meta × rubrica
 * ativa, zeros inclusive: filtrar por uma Meta sem orçamento devolve 6 linhas
 * zeradas, nunca uma lista vazia. Sem este predicado a tela mostraria uma
 * matriz de "R$ 0,00" onde o correto é dizer que não há orçamento.
 *
 * `saldo_disponivel` fica de fora do teste de propósito: é derivado dos outros
 * quatro (aprovado − distribuído − comprometido − executado), então já é zero
 * sempre que eles são.
 */
export function linhaVazia(linha: PainelOrcamentoLinhaApi): boolean {
  return (
    valorNumerico(linha.valor_aprovado) === 0 &&
    valorNumerico(linha.valor_distribuido) === 0 &&
    valorNumerico(linha.valor_comprometido) === 0 &&
    valorNumerico(linha.valor_executado) === 0
  );
}

// ─── Rótulos de nível ───────────────────────────────────────────────────────

const NIVEL_LABEL: Record<NivelOrcamento, string> = {
  nacional: "Nacional",
  estadual: "Estadual",
  territorial: "Territorial",
};

export function nivelOrcamentoLabel(nivel: NivelOrcamento): string {
  return NIVEL_LABEL[nivel];
}

/**
 * Escopo exibido no cabeçalho e no <caption> da matriz: "Nacional",
 * "Estado: Pernambuco", "Território: Sertão do Pajeú". Sem o nome do local
 * (opções ainda carregando) degrada para o rótulo do nível.
 */
export function descreverEscopo(
  nivel: NivelOrcamento,
  nomeLocal: string | null,
): string {
  if (nivel === "nacional") return "Nacional";
  if (!nomeLocal) return NIVEL_LABEL[nivel];
  return nivel === "estadual"
    ? `Estado: ${nomeLocal}`
    : `Território: ${nomeLocal}`;
}

// ─── Escrita: distribuição orçamentária (§5.3.2) ────────────────────────────

/**
 * Payload de `POST /sgp/metas/{id}/orcamento/alocacoes/`.
 *
 * Os sufixos `_id` são do próprio contrato (`BudgetAllocationCreateSerializer`
 * declara `rubrica_id`, `estado_id`, `territorio_id` com `source=`), não uma
 * convenção nossa — mandar `rubrica` em vez de `rubrica_id` dá 400.
 *
 * `reserva_ugp` fica de fora: só se aplica ao nível nacional, que esta tela não
 * grava.
 */
export type CriarAlocacaoPayload = {
  rubrica_id: number;
  nivel: Exclude<NivelOrcamento, "nacional">;
  /** Obrigatório no nível estadual; ausente no territorial. */
  estado_id?: number;
  /** Obrigatório no nível territorial; ausente no estadual. */
  territorio_id?: number;
  /** Decimal em string, como o DRF espera: "1234.56". */
  valor_alocado: string;
};

/**
 * POST /api/v1/sgp/metas/{id}/orcamento/alocacoes/
 *
 * Erros de teto chegam como 400 com `{"valor_alocado": "..."}`, que o
 * `normalizeErrorBody` de lib/api já converte em `ApiError.fieldErrors` — a
 * tela ancora a mensagem no input em vez de mostrar um alerta solto.
 */
export async function criarAlocacao(
  metaId: number,
  payload: CriarAlocacaoPayload,
): Promise<AlocacaoApi> {
  const res = await apiClient(`/api/v1/sgp/metas/${metaId}/orcamento/alocacoes/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/**
 * PATCH /api/v1/sgp/orcamento/alocacoes/{id}/ — só o valor muda.
 *
 * Reduzir abaixo de comprometido+executado é recusado pelo service com a
 * mensagem e o mínimo exato, também em `valor_alocado`.
 */
export async function atualizarAlocacao(
  alocacaoId: number,
  valorAlocado: string,
): Promise<AlocacaoApi> {
  const res = await apiClient(`/api/v1/sgp/orcamento/alocacoes/${alocacaoId}/`, {
    method: "PATCH",
    body: JSON.stringify({ valor_alocado: valorAlocado }),
  });
  return res.json();
}

// ─── Saldo por rubrica no território (Issue #232) ───────────────────────────

/**
 * Razão do bloqueio de uma rubrica sem saldo.
 *
 * Espelha `BLOQUEIO_SALDO_ZERO` em `apps/sgp/services/budget.py`. O painel NÃO
 * devolve `motivo_bloqueio` — quem devolve é `GET /sgp/orcamento/saldo/`, que
 * exige `meta`, `rubrica` e `valor` obrigatórios e responderia uma pergunta por
 * vez (seis chamadas para montar este card). Como o texto é fixo no backend,
 * espelhá-lo aqui custa uma constante e evita o N+1; mesma escolha já feita
 * para as choices do SGP em `lib/choices.ts`.
 */
export const BLOQUEIO_SALDO_ZERO =
  "Bloqueado para novas solicitações quando saldo da rubrica é zero.";

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
 * As rubricas de UMA Meta, com o saldo do nível que o perfil do usuário alcança.
 *
 * O painel devolve a matriz inteira (Metas × rubricas); filtrar por Meta no
 * backend é o que reduz as 42 linhas às 6 que o card mostra. A Meta é
 * obrigatória de propósito: cada uma tem teto próprio, então somar uma rubrica
 * entre Metas produziria um número que não autoriza gasto nenhum — e a demanda
 * do SGD é sempre por Meta + Rubrica, como mostra a assinatura de
 * `SaldoConsultaView`.
 *
 * Para o ADT/ACR o backend resolve o nível como territorial sem receber filtro.
 * Não chame esta função para um ADT sem território: `resolver_nivel_painel`
 * responde 403, com a mesma mensagem de quem não tem acesso algum ao orçamento
 * — a distinção tem de sair da sessão, ver `BudgetBalance`.
 */
export async function fetchSaldoPorRubrica(
  metaId: number | string,
  signal?: AbortSignal,
): Promise<SaldoRubrica[]> {
  const linhas = await fetchPainelOrcamento({ meta: String(metaId) }, signal);

  return linhas.map((linha) => {
    const saldoNumero = Number(linha.saldo_disponivel);
    const numero = Number.isNaN(saldoNumero) ? 0 : saldoNumero;
    return {
      rubrica: linha.rubrica,
      saldo: linha.saldo_disponivel,
      saldoNumero: numero,
      bloqueada: numero <= 0,
      negativa: numero < 0,
    };
  });
}
