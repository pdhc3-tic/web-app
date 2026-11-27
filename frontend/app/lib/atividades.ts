import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { Refinar, Schema } from "@/app/lib/apiSchema";
import type { NestedRef } from "@/app/lib/ufpas";
import type { BadgeStatus } from "@/app/components/ui/Badge/Badge";

// ─── Regras de status espelhadas do backend ──────────────────────────────────
// As LISTAS de tipo, forma de atuação, âmbito e status vêm de `useSgpChoices()`
// (#272); o rótulo de um status, de `useRotuloChoice("status_atividade")`.

/**
 * Status que tornam a Justificativa obrigatória.
 * Espelha `status_exige_justificativa` em ActivityDetailSerializer.validate().
 */
export const STATUS_EXIGE_JUSTIFICATIVA = ["nao_realizada", "cancelada"];

/**
 * Únicos status aceitos na criação. Espelha
 * ActivityDetailSerializer._validate_status_transition() quando instance é None.
 */
export const STATUS_INICIAIS = ["planejado", "agendado"];

/**
 * Status da API (snake_case) → variante do <Badge> (kebab-case).
 *
 * Mapa explícito de propósito: `concluido_sem_evidencia` vira `sem-evidencia`,
 * então trocar `_` por `-` não resolveria. Status desconhecido cai em
 * `planejado` para a listagem não quebrar se o backend criar um estado novo.
 */
const BADGE_STATUS: Record<string, BadgeStatus> = {
  planejado: "planejado",
  agendado: "agendado",
  em_andamento: "em-andamento",
  concluido: "concluido",
  concluido_sem_evidencia: "sem-evidencia",
  adiada: "adiada",
  nao_realizada: "nao-realizada",
  cancelada: "cancelada",
};

export function badgeStatusFor(status: string): BadgeStatus {
  return BADGE_STATUS[status] ?? "planejado";
}

// ─── Tipos ───────────────────────────────────────────────────────────────────

// ─── Tipos ──────────────────────────────────────────────────────────────────

/**
 * Os tipos vêm do schema (#273).
 */

/**
 * Ação do Plano de Trabalho (`WorkPlanAcaoList`, subset usado aqui), com a
 * Meta, a Submeta e o Indicador nomeados (#445) para o formulário mostrar a
 * cadeia assim que a Ação é escolhida (#446).
 */
export type AcaoPT = Pick<
  Schema<"WorkPlanAcaoList">,
  | "id"
  | "meta"
  | "submeta"
  | "indicador"
  | "numero"
  | "descricao"
  | "meta_numero"
  | "meta_titulo"
  | "submeta_numero"
  | "submeta_titulo"
> & {
  indicador_detalhe: Pick<Schema<"PlanoTrabalhoIndicadorRef">, "codigo" | "nome" | "unidade_medida">;
};

/** `TecnicoOption` — opções do filtro por técnico. */
export type TecnicoOption = Schema<"TecnicoOption">;

/**
 * Ação aninhada no detalhe (`AcaoDaAtividade`): a cadeia Meta → Submeta →
 * Ação → Indicador do Plano de Trabalho.
 */
export type AcaoNested = Schema<"AcaoDaAtividade">;

/** Técnico aninhado no detalhe. */
export type TecnicoNested = {
  id: number;
  nome: string;
  email: string;
};

/**
 * `ActivityListSerializer`.
 *
 * Refinamentos: `tipo_atividade`, `forma_atuacao`, `ambito` e `status` passam
 * dos enums estreitos do schema para `string`, compatível com o restante do
 * código. `municipio` mantém o tipo `MunicipioNested` do schema (`.nome` para
 * exibição, como no restante das telas de atividade).
 */
export type AtividadeListItem = Refinar<
  Schema<"ActivityList">,
  {
    tipo_atividade: string;
    forma_atuacao: string;
    ambito: string;
    status: string;
  }
>;

/**
 * Espelha apps/sgp/serializers.py::ActivityDetailSerializer (leitura).
 * Atenção ao `to_representation`: `municipio`, `comunidade`, `acao` e
 * `tecnico_responsavel` voltam como objetos aninhados, mas são ENVIADOS como
 * PK na escrita. Os M2M continuam como arrays de PK na leitura.
 */
/** UFPA participante, como vem no detalhe consolidado (Issue #227). */
export type UfpaParticipante = {
  id: number;
  nome_titular: string;
  /** Mascarado pelo backend ("105.***.***-30"). */
  cpf: string;
  foto_url: string;
  ativo: boolean;
  municipio: { id: number; nome: string };
  territorio: { id: number; nome: string } | null;
  criado_em: string;
};

/** Membro participante, como vem no detalhe consolidado (Issue #227). */
export type MembroParticipante = {
  id: number;
  nome_completo: string;
  cpf: string;
  data_nascimento: string | null;
  idade: number | null;
  grau_parentesco: string;
  grau_parentesco_display: string;
  genero: number | null;
  genero_display: string;
  cor_raca: number | null;
  cor_raca_display: string;
  saude: string[];
  criado_em: string;
};

/**
 * `ActivityDetailSerializer` (leitura) — `ActivityDetailResposta` no schema.
 *
 * Refinamentos:
 * - `acao` usa o tipo local `AcaoNested` (mantém a shape histórica).
 * - `tecnico_responsavel` e `equipe_adicional` usam `TecnicoNested`.
 * - `municipio` refinado de `MunicipioNested` para `NestedRef` (shape anterior).
 * - `ufpas_participantes`, `membros_participantes` usam os tipos locais.
 * - `google_calendar_sync_status` refinado de enum para union literal.
 * - `status`, `tipo_atividade`, `ambito`, `forma_atuacao` refinados para `string`.
 * - `transicoes_permitidas` refinado de enum[] para `string[]`.
 */
export type AtividadeDetail = Refinar<
  Schema<"ActivityDetailResposta">,
  {
    acao: AcaoNested;
    tecnico_responsavel: TecnicoNested;
    equipe_adicional: TecnicoNested[];
    municipio: NestedRef;
    ufpas_participantes: UfpaParticipante[];
    membros_participantes: MembroParticipante[];
    google_calendar_sync_status: "pendente" | "ok" | "erro";
    tipo_atividade: string;
    forma_atuacao: string;
    ambito: string;
    status: string;
    transicoes_permitidas: string[];
    custo_previsto: string;
    custo_realizado: string;
    /** Sempre presente na resposta (string vazia quando não preenchido). */
    parceiros_livres: string;
    resultados_alcancados: string;
    justificativa: string;
    ativo: boolean;
  }
>;

/**
 * Campos graváveis (POST/PATCH) — `ActivityDetailRequest` do schema.
 *
 * Refinamentos:
 * - `tipo_atividade`, `forma_atuacao`, `ambito`, `status` passam dos enums
 *   estreitos do schema para `string`, compatível com o restante do código.
 * - `acao`, `tecnico_responsavel` e `municipio` passam de required para
 *   `number | null`: o formulário inicia com null e envia null enquanto o
 *   usuário não escolheu — o backend valida na save, não aqui.
 */
export type AtividadeWritePayload = Refinar<
  Schema<"ActivityDetailRequest">,
  {
    tipo_atividade: string;
    /** FK obrigatória, mas null no estado inicial do formulário. */
    acao: number | null;
    forma_atuacao: string;
    /** FK obrigatória, mas null no estado inicial do formulário. */
    tecnico_responsavel: number | null;
    /** FK obrigatória, mas null no estado inicial do formulário. */
    municipio: number | null;
    ambito: string;
    status: string;
    /**
     * `parceiros_organizacoes` fica FORA do payload de propósito. O formulário
     * não tem seletor de organizações, e mandar `[]` a cada PATCH apagaria os
     * vínculos criados por outro caminho — o serializer só toca no M2M quando a
     * chave vem, então omiti-la é o que preserva o que já está lá.
     */
  }
>;

// ─── API — Listagem ──────────────────────────────────────────────────────────

/**
 * Filtros da listagem. Os nomes aqui são os da UI; a tradução para os
 * parâmetros do ActivityFilter acontece em buildAtividadesQuery().
 */
export type ListAtividadesParams = {
  /** Contrato offset/limit do componente Pagination — convertido para page/page_size. */
  limit: number;
  offset: number;
  acao?: string;
  /** Plano de Trabalho (#464): ids de Meta, Submeta e Indicador. */
  meta?: string;
  submeta?: string;
  indicador?: string;
  projeto?: string;
  territorio?: string;
  tecnico?: string;
  tipo?: string;
  status?: string;
  /** Datas no formato YYYY-MM-DD (input nativo), aplicadas sobre data_inicio. */
  inicioDe?: string;
  inicioAte?: string;
  ordering?: string;
  atrasada?: boolean;
};

/**
 * Monta a query string da listagem.
 *
 * Dois cuidados que não dão erro visível quando esquecidos:
 * 1. O ActivityViewSet usa ActivityPagination (PageNumberPagination), que lê
 *    `page`/`page_size` — mandar limit/offset seria silenciosamente ignorado e
 *    devolveria sempre a primeira página.
 * 2. O ActivityFilter chama os filtros de `territorio_id` e `tecnico_id`, e não
 *    `territorio`/`tecnico` como o UFPAFilter. Nome errado é ignorado pelo
 *    django-filter, que então devolve a lista inteira sem filtrar.
 */
export function buildAtividadesQuery(params: ListAtividadesParams): string {
  const qs = new URLSearchParams();

  qs.set("page", String(Math.floor(params.offset / params.limit) + 1));
  qs.set("page_size", String(params.limit));

  if (params.acao) qs.set("acao", params.acao);
  if (params.meta) qs.set("meta", params.meta);
  if (params.submeta) qs.set("submeta", params.submeta);
  if (params.indicador) qs.set("indicador", params.indicador);
  if (params.projeto) qs.set("projeto", params.projeto);
  if (params.territorio) qs.set("territorio_id", params.territorio);
  if (params.tecnico) qs.set("tecnico_id", params.tecnico);
  if (params.tipo) qs.set("tipo_atividade", params.tipo);
  if (params.status) qs.set("status", params.status);
  if (params.inicioDe) qs.set("data_inicio_after", params.inicioDe);
  if (params.inicioAte) qs.set("data_inicio_before", params.inicioAte);
  if (params.atrasada != null) qs.set("atrasada", String(params.atrasada));
  qs.set("ordering", params.ordering ?? "-data_inicio");

  return qs.toString();
}

/** GET /api/v1/sgp/atividades/ — listagem paginada com filtros. */
export async function listAtividades(
  params: ListAtividadesParams,
  signal?: AbortSignal,
): Promise<Paginated<AtividadeListItem>> {
  const res = await apiClient(
    `/api/v1/sgp/atividades/?${buildAtividadesQuery(params)}`,
    { signal },
  );
  return res.json();
}

/** GET /api/v1/sgp/atividades/?page_size=1 — retorna apenas a contagem. */
export async function fetchAtividadeCount(
  params: { status?: string; atrasada?: boolean; territorioId?: string },
  signal?: AbortSignal,
): Promise<number> {
  const qs = new URLSearchParams({ page_size: "1" });
  if (params.status) qs.set("status", params.status);
  if (params.atrasada != null) qs.set("atrasada", String(params.atrasada));
  if (params.territorioId) qs.set("territorio_id", params.territorioId);
  const res = await apiClient(`/api/v1/sgp/atividades/?${qs}`, { signal });
  const data: Paginated<AtividadeListItem> = await res.json();
  return data.count;
}

// ─── API — Atividade ─────────────────────────────────────────────────────────

/** GET /api/v1/sgp/atividades/{id}/ — detalhe completo. Lança ApiError (404/403). */
export async function getAtividade(
  id: string | number,
  signal?: AbortSignal,
): Promise<AtividadeDetail> {
  const res = await apiClient(`/api/v1/sgp/atividades/${id}/`, { signal });
  return res.json();
}

/** POST /api/v1/sgp/atividades/ — cria a atividade; retorna o detalhe com id. */
export async function createAtividade(
  payload: AtividadeWritePayload,
): Promise<AtividadeDetail> {
  const res = await apiClient("/api/v1/sgp/atividades/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /api/v1/sgp/atividades/{id}/ — atualiza a atividade. */
export async function updateAtividade(
  id: string | number,
  payload: AtividadeWritePayload,
): Promise<AtividadeDetail> {
  const res = await apiClient(`/api/v1/sgp/atividades/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ─── API — Dados relacionados ────────────────────────────────────────────────

const ACOES_PAGE_SIZE = 200; // max_page_size da UFPAPagination
const ACOES_MAX_PAGES = 10;

/**
 * GET /api/v1/acoes/ — todas as Ações do PT no escopo do usuário.
 *
 * O WorkPlanAcaoViewSet não tem SearchFilter nem filtro `q`, então não há busca
 * por texto no servidor: carregamos a lista inteira (paginando até o teto) e o
 * combobox filtra em memória. Se o volume de ações crescer muito, o backend
 * precisa expor busca — ver a nota no README da feature.
 */
export async function listAcoes(signal?: AbortSignal): Promise<AcaoPT[]> {
  const acoes: AcaoPT[] = [];
  for (let page = 1; page <= ACOES_MAX_PAGES; page++) {
    const res = await apiClient(
      `/api/v1/acoes/?page=${page}&page_size=${ACOES_PAGE_SIZE}&ordering=numero`,
      { signal },
    );
    const data: Paginated<AcaoPT> = await res.json();
    acoes.push(...data.results);
    if (!data.next) break;
  }
  return acoes;
}

/**
 * GET /api/v1/users/ — opções de técnico.
 *
 * O UserViewSet do backend é `IsSuperAdmin`, então esta chamada retorna 403 para
 * ADT/ACR e articuladores — justamente quem mais registra atividades. Em erro
 * devolvemos [] e a UI cai para o modo degradado (só o usuário logado como
 * responsável, equipe adicional desabilitada).
 */
export async function listTecnicos(
  signal?: AbortSignal,
): Promise<TecnicoOption[]> {
  try {
    const res = await apiClient("/api/v1/users/?limit=500&ativo=true", {
      signal,
    });
    const data: Paginated<{ id: number; nome_completo: string; email: string }> =
      await res.json();
    return data.results.map((u) => ({ id: u.id, nome: u.nome_completo, email: u.email }));
  } catch {
    return [];
  }
}

// ─── Transição guiada de status (Issue #234) ────────────────────────────────

/**
 * Status terminais: `STATUS_TRANSITIONS[status]` é vazio no backend, então
 * nenhuma saída é possível. Espelha os `set()` de models/activity.py.
 */
export const STATUS_TERMINAIS = [
  "concluido",
  "concluido_sem_evidencia",
  "nao_realizada",
  "cancelada",
];

/** True quando a atividade não admite mais nenhuma transição. */
export function isStatusTerminal(status: string): boolean {
  return STATUS_TERMINAIS.includes(status);
}

/**
 * O que o destino escolhido exige antes de submeter.
 *
 * `justificativa` e `evidencia` espelham regras que o backend REALMENTE aplica
 * (ActivityDetailSerializer.validate). `novaData` é a exceção: a Issue #234
 * pede a exigência ao sair de "Adiada", mas nenhuma validação equivalente
 * existe no servidor — confirmado por PATCH direto, que devolve 200 sem data
 * nova. Enquanto isso não mudar, a regra vale só nesta tela e uma chamada
 * direta à API a contorna. Registrado em docs/pendencias-backend-sprint-9.md.
 */
export type ExigenciaTransicao = {
  justificativa: boolean;
  novaData: boolean;
  evidencia: boolean;
};

export function exigenciasDaTransicao(
  statusAtual: string,
  destino: string,
): ExigenciaTransicao {
  return {
    justificativa: STATUS_EXIGE_JUSTIFICATIVA.includes(destino),
    novaData: statusAtual === "adiada" && destino === "agendado",
    evidencia: destino === "concluido",
  };
}

/** Payload da transição — só o que muda, para não reenviar a atividade toda. */
export type TransicaoPayload = {
  status: string;
  justificativa?: string;
  data_inicio?: string;
  data_fim?: string;
};

/**
 * PATCH /api/v1/sgp/atividades/{id}/ — aplica só a transição de status.
 *
 * Parcial de propósito: o modal não carrega o formulário inteiro, e mandar
 * campos não tocados arriscaria sobrescrever edição concorrente.
 */
export async function transicionarStatus(
  id: string | number,
  payload: TransicaoPayload,
): Promise<AtividadeDetail> {
  const res = await apiClient(`/api/v1/sgp/atividades/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}
