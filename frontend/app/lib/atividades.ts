import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { NestedRef } from "@/app/lib/upfs";
import type { BadgeStatus } from "@/app/components/ui/Badge/Badge";

// ─── Constantes espelhadas do backend ────────────────────────────────────────
// Fonte: apps/sgp/models/activity.py.
//
// Servem de FALLBACK em @/app/lib/choices.ts: o SGPChoicesView
// (GET /api/v1/choices/) ainda não expõe os choices de atividade, então
// enquanto isso a UI usa estas listas. Assim que o backend incluir as chaves
// `tipo_atividade`, `forma_atuacao`, `ambito` e `status`, elas passam a valer
// automaticamente e estas constantes viram só rede de segurança.
//
// Em componente, use `useSgpChoices()` em vez destas constantes.

/** Espelha TIPO_ATIVIDADE_CHOICES. */
export const TIPO_ATIVIDADE_OPTIONS = [
  { value: "visita_tecnica", label: "Visita técnica" },
  { value: "reuniao_comunitaria", label: "Reunião comunitária" },
  { value: "oficina", label: "Oficina" },
  { value: "intercambio", label: "Intercâmbio" },
  { value: "curso_capacitacao", label: "Curso/Capacitação" },
  { value: "dia_de_campo", label: "Dia de campo" },
  { value: "seminario", label: "Seminário" },
  { value: "encontro", label: "Encontro" },
  { value: "dia_de_partilha", label: "Dia de partilha" },
  { value: "atividade_interna", label: "Atividade interna" },
  { value: "pesquisa_de_campo", label: "Pesquisa de campo" },
  { value: "ater", label: "Assistência técnica/ATER" },
  { value: "outro", label: "Outro" },
];

/** Espelha FORMA_ATUACAO_CHOICES. */
export const FORMA_ATUACAO_OPTIONS = [
  { value: "realizacao", label: "Realização" },
  { value: "participacao", label: "Participação" },
  { value: "apoio", label: "Apoio" },
  { value: "articulacao", label: "Articulação" },
];

/** Espelha AMBITO_CHOICES. */
export const AMBITO_OPTIONS = [
  { value: "municipal", label: "Municipal" },
  { value: "microrregional", label: "Microrregional" },
  { value: "estadual", label: "Estadual" },
  { value: "supraestadual", label: "Supraestadual" },
];

/** Espelha STATUS_CHOICES. */
export const STATUS_OPTIONS = [
  { value: "planejado", label: "Planejado" },
  { value: "agendado", label: "Agendado" },
  { value: "em_andamento", label: "Em andamento" },
  { value: "concluido", label: "Concluído" },
  { value: "concluido_sem_evidencia", label: "Concluído sem evidência" },
  { value: "adiada", label: "Adiada" },
  { value: "nao_realizada", label: "Não realizada" },
  { value: "cancelada", label: "Cancelada" },
];

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

export function statusLabel(value: string): string {
  return STATUS_OPTIONS.find((s) => s.value === value)?.label ?? value;
}

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

/** Ação do Plano de Trabalho (WorkPlanAcaoListSerializer, subset usado aqui). */
export type AcaoPT = {
  id: number;
  meta: number;
  numero: string;
  descricao: string;
};

/** Técnico/usuário para os campos de equipe. */
export type TecnicoOption = {
  id: number;
  nome: string;
};

/** Ação aninhada no detalhe (to_representation do ActivityDetailSerializer). */
export type AcaoNested = {
  id: number;
  numero: string;
  descricao: string;
};

/** Técnico aninhado no detalhe. */
export type TecnicoNested = {
  id: number;
  nome: string;
  email: string;
};

/**
 * Espelha apps/sgp/serializers.py::ActivityListSerializer.
 * `municipio` vem como PK e `municipio_nome` como texto; idem para o técnico.
 * `atrasada` já é calculado no backend (false para status terminais).
 */
export type AtividadeListItem = {
  id: number;
  titulo: string;
  tipo_atividade: string;
  tipo_atividade_display: string;
  forma_atuacao: string;
  ambito: string;
  ambito_display: string;
  municipio: number;
  municipio_nome: string;
  data_inicio: string;
  data_fim: string;
  status: string;
  status_display: string;
  tecnico_responsavel: number;
  tecnico_nome: string;
  total_participantes: number;
  atrasada: boolean;
  ativo: boolean;
  criado_em: string;
};

/**
 * Espelha apps/sgp/serializers.py::ActivityDetailSerializer (leitura).
 * Atenção ao `to_representation`: `municipio`, `comunidade`, `acao` e
 * `tecnico_responsavel` voltam como objetos aninhados, mas são ENVIADOS como
 * PK na escrita. Os M2M continuam como arrays de PK na leitura.
 */
/** UPF participante, como vem no detalhe consolidado (Issue #227). */
export type UpfParticipante = {
  id: number;
  nome_titular: string;
  /** Mascarado pelo backend ("105.***.***-30"). */
  cpf: string;
  foto_url: string;
  ativa: boolean;
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

export type AtividadeDetail = {
  id: number;
  titulo: string;
  tipo_atividade: string;
  tipo_atividade_display: string;
  acao: AcaoNested;
  forma_atuacao: string;
  forma_atuacao_display: string;
  tecnico_responsavel: TecnicoNested;
  /**
   * Objetos na LEITURA, ids na escrita — mesma assimetria de
   * `upfs_participantes`. `to_representation` do ActivityDetailSerializer
   * reescreve o M2M como `{id, nome, email}`; o tipo dizia `number[]` e por
   * isso o prefill da edição entregava objetos ao seletor de ids.
   */
  equipe_adicional: TecnicoNested[];
  municipio: NestedRef;
  territorio_id: number | null;
  comunidade: NestedRef | null;
  ambito: string;
  ambito_display: string;
  latitude: string | null;
  longitude: string | null;
  data_inicio: string;
  data_fim: string;
  /**
   * Objetos, NÃO ids — o detalhe passou a devolver o registro inteiro na Issue
   * #227 (backend, 05/09). O tipo antigo dizia `number[]`, e por causa disso o
   * prefill da edição chegou a montar `/api/v1/upfs/[object Object]/`.
   * A ESCRITA continua enviando ids (ver AtividadeWritePayload).
   */
  upfs_participantes: UpfParticipante[];
  membros_participantes: MembroParticipante[];
  total_participantes: number;
  /**
   * Espelha GOOGLE_CALENDAR_SYNC_STATUS_CHOICES em models/activity.py.
   * `erro` é só um aviso na ficha (RF24): a atividade está salva, o que falhou
   * foi criar o evento na agenda.
   */
  google_calendar_sync_status: "pendente" | "ok" | "erro";
  /**
   * Evidências vinculadas, como vêm no detalhe consolidado (Issue #227).
   *
   * O tipo declara só o que a UI consome — a presença de ao menos um item é o
   * que decide se "Concluído" pode ser oferecido. A galeria carrega os dados
   * completos por conta própria, pelos endpoints de fotos/documentos.
   */
  fotos?: { id: number; arquivo_url: string; legenda: string; ordem: number }[];
  documentos?: { id: number; nome_original: string; tipo: string }[];
  /**
   * Ids das `core.Organization` parceiras. O detalhe NÃO aninha nome — só o
   * M2M cru —, e `OrganizationViewSet` restringe a listagem a
   * super-admin/UGP/Articulador, então o ADT não tem como resolvê-los.
   * Pedido aberto ao backend em docs/pendencias-backend-sprint-9.md.
   */
  parceiros_organizacoes: number[];
  /** Parceiros em texto livre — o campo que o formulário preenche. */
  parceiros_livres: string;
  descricao_narrativa: string;
  resultados_alcancados: string;
  status: string;
  status_display: string;
  justificativa: string;
  atrasada: boolean;
  /** Status para os quais o backend aceita transitar a partir do atual. */
  transicoes_permitidas: string[];
  ativo: boolean;
  criado_por: number | null;
  criado_em: string;
  atualizado_em: string;
  // ── Procedência SCA ────────────────────────────────────────────────────────
  // Espelham os campos de sync do backend. `ultima_origem` é o que vale para a
  // badge: `device_id` fica preenchido para sempre depois do primeiro sync,
  // inclusive quando a última edição veio da web.
  device_id: string;
  uuid_local: string | null;
  ultima_origem: "sca" | "web";
  ultimo_sync_em: string | null;

};

/** Campos graváveis (POST/PATCH). FKs e M2M vão como PK. */
export type AtividadeWritePayload = {
  titulo: string;
  tipo_atividade: string;
  acao: number | null;
  forma_atuacao: string;
  tecnico_responsavel: number | null;
  equipe_adicional: number[];
  municipio: number | null;
  comunidade: number | null;
  ambito: string;
  latitude: string | null;
  longitude: string | null;
  data_inicio: string;
  data_fim: string;
  /** Na escrita são ids: o serializer usa PrimaryKeyRelatedField. */
  upfs_participantes: number[];
  membros_participantes: number[];
  /**
   * `parceiros` não existe no serializer: o campo é `parceiros_livres`. O
   * formulário enviava a chave antiga, o DRF a descartava em silêncio e o que
   * o técnico digitava nunca chegava ao banco.
   *
   * `parceiros_organizacoes` fica FORA do payload de propósito. O formulário
   * não tem seletor de organizações, e mandar `[]` a cada PATCH apagaria os
   * vínculos criados por outro caminho — o serializer só toca no M2M quando a
   * chave vem, então omiti-la é o que preserva o que já está lá.
   */
  parceiros_livres: string;
  descricao_narrativa: string;
  resultados_alcancados: string;
  status: string;
  justificativa: string;
};

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
  projeto?: string;
  territorio?: string;
  tecnico?: string;
  tipo?: string;
  status?: string;
  /** Datas no formato YYYY-MM-DD (input nativo), aplicadas sobre data_inicio. */
  inicioDe?: string;
  inicioAte?: string;
  ordering?: string;
};

/**
 * Monta a query string da listagem.
 *
 * Dois cuidados que não dão erro visível quando esquecidos:
 * 1. O ActivityViewSet usa ActivityPagination (PageNumberPagination), que lê
 *    `page`/`page_size` — mandar limit/offset seria silenciosamente ignorado e
 *    devolveria sempre a primeira página.
 * 2. O ActivityFilter chama os filtros de `territorio_id` e `tecnico_id`, e não
 *    `territorio`/`tecnico` como o UPFFilter. Nome errado é ignorado pelo
 *    django-filter, que então devolve a lista inteira sem filtrar.
 */
function buildAtividadesQuery(params: ListAtividadesParams): string {
  const qs = new URLSearchParams();

  qs.set("page", String(Math.floor(params.offset / params.limit) + 1));
  qs.set("page_size", String(params.limit));

  if (params.acao) qs.set("acao", params.acao);
  if (params.projeto) qs.set("projeto", params.projeto);
  if (params.territorio) qs.set("territorio_id", params.territorio);
  if (params.tecnico) qs.set("tecnico_id", params.tecnico);
  if (params.tipo) qs.set("tipo_atividade", params.tipo);
  if (params.status) qs.set("status", params.status);
  if (params.inicioDe) qs.set("data_inicio_after", params.inicioDe);
  if (params.inicioAte) qs.set("data_inicio_before", params.inicioAte);
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

const ACOES_PAGE_SIZE = 200; // max_page_size da UPFPagination
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
    const data: Paginated<{ id: number; nome_completo: string }> =
      await res.json();
    return data.results.map((u) => ({ id: u.id, nome: u.nome_completo }));
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
