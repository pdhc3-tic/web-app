import { apiClient } from "@/app/lib/api";

/**
 * Catálogo de tipos de solicitação do SGD (#365), sobre
 * `/api/v1/sgd/config/tipos-solicitacao/` (#357): leitura para qualquer
 * usuário logado, escrita só para o Super Admin.
 *
 * Cada tipo liga um identificador (`slug`) a uma rubrica e descreve os campos
 * do formulário num JSON Schema (`schema_campos`), que o backend usa para
 * validar o `campos_json` da solicitação. Os seis tipos de origem têm layout
 * próprio no front (`CONFIG_POR_TIPO`); um tipo novo é desenhado a partir do
 * schema (`configDoSchema`, em `camposSolicitacao.ts`).
 */

/** Uma propriedade do `schema_campos`, no subconjunto que o formulário entende. */
export type PropriedadeSchema = {
  type?: string | string[];
  title?: string;
  description?: string;
  format?: string;
  enum?: (string | number)[];
  oneOf?: { const: string | number; title?: string }[];
  minimum?: number;
  maxLength?: number;
  /** Mensagem própria da regra, que o backend devolve no erro. */
  mensagem?: string;
  /** Convenção do front: a ordem do campo no formulário (o JSONB não guarda a ordem das chaves). */
  "x-ordem"?: number;
};

export type SchemaCampos = {
  type?: string;
  required?: string[];
  properties?: Record<string, PropriedadeSchema>;
};

/** `TipoSolicitacaoSerializer`. */
export type TipoSolicitacaoCatalogo = {
  id: number;
  slug: string;
  nome: string;
  rubrica: number;
  rubrica_nome: string;
  schema_campos: SchemaCampos;
  /** Estratégia registrada no backend (CPF, cálculo de diárias, cotações); vazio num tipo novo. */
  validador: string;
  ativo: boolean;
  ordem: number;
  criado_em: string;
  atualizado_em: string;
};

export type TipoSolicitacaoPayload = {
  slug: string;
  nome: string;
  rubrica: number;
  schema_campos: SchemaCampos;
  ativo: boolean;
  ordem: number;
};

/** Rubrica do catálogo do orçamento (`GET /sgp/rubricas/`). */
export type Rubrica = { id: number; slug: string; nome: string; ativo: boolean };

const BASE = "/api/v1/sgd/config/tipos-solicitacao/";

/** Os tipos do catálogo, na ordem cadastrada. Sem `apenasAtivos`, vêm também os inativos. */
export async function listTiposSolicitacao(
  { apenasAtivos }: { apenasAtivos: boolean },
  signal?: AbortSignal,
): Promise<TipoSolicitacaoCatalogo[]> {
  const res = await apiClient(apenasAtivos ? `${BASE}?ativo=true` : BASE, { signal });
  const tipos = (await res.json()) as TipoSolicitacaoCatalogo[];
  return [...tipos].sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome, "pt-BR"));
}

export async function criarTipoSolicitacao(payload: TipoSolicitacaoPayload): Promise<TipoSolicitacaoCatalogo> {
  const res = await apiClient(BASE, { method: "POST", body: JSON.stringify(payload) });
  return res.json();
}

/** `slug` e `validador` não mudam depois de criados: o backend recusa. */
export async function atualizarTipoSolicitacao(
  id: number,
  payload: Partial<Omit<TipoSolicitacaoPayload, "slug">>,
): Promise<TipoSolicitacaoCatalogo> {
  const res = await apiClient(`${BASE}${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
  return res.json();
}

/** Só sem solicitações; com elas, o backend responde 400 e pede para desativar. */
export async function removerTipoSolicitacao(id: number): Promise<void> {
  await apiClient(`${BASE}${id}/`, { method: "DELETE" });
}

/** `GET /api/v1/sgp/rubricas/`, com as inativas, para nomear a rubrica de um tipo antigo. */
export async function listRubricas(signal?: AbortSignal): Promise<Rubrica[]> {
  const res = await apiClient("/api/v1/sgp/rubricas/", { signal });
  return res.json();
}

/** Identificador válido para um tipo novo: minúsculas, números, hífen e sublinhado. */
export const PADRAO_SLUG = /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/;

/** Schema inicial de um tipo novo no editor: um campo de texto obrigatório, como exemplo. */
export const SCHEMA_INICIAL: SchemaCampos = {
  type: "object",
  required: ["descricao"],
  properties: {
    descricao: { type: "string", title: "Descrição", "x-ordem": 1 },
  },
};
