import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";

/**
 * Conflitos de sincronização do SCA (BE-11).
 *
 * Um conflito nasce quando o aplicativo de campo envia um valor divergente do
 * que está no servidor. Campos sensíveis (nome, CPF, coordenadas) ficam
 * `pendente` e exigem decisão humana; os demais o backend já resolve sozinho e
 * registra como `resolvido_auto`.
 *
 * O recorte é do servidor: Super Admin e UGP veem tudo, o Articulador Estadual
 * vê apenas os territórios dos seus estados, e os demais perfis recebem lista
 * vazia (`ConflictLogViewSet.get_queryset`). A tela não filtra por conta
 * própria — apenas apresenta o que a API devolve.
 */

// ─── Contrato do endpoint ────────────────────────────────────────────────────

/** Espelha apps/sca/models.py::ConflictLog.Status. */
export type ConflitoStatus = "pendente" | "resolvido_auto" | "resolvido_manual";

/** Entidades sincronizáveis — ConflictLogFilter aceita exatamente estas três. */
export type ConflitoEntidade = "upf" | "member" | "activity";

/** Espelha ConflictResolveSerializer.decisao. */
export type ConflitoDecisao = "local" | "servidor" | "manual";

/**
 * Os valores trafegam em JSONField: o backend grava o que veio do campo, então
 * pode ser texto, número, booleano ou nulo.
 */
export type ValorConflito =
  | string
  | number
  | boolean
  | null
  | Record<string, unknown>;

export type ConflitoPessoa = { id: number; nome: string; email: string };

/** Espelha apps/sca/serializers.py::ConflictLogListSerializer. */
export type Conflito = {
  id: number;
  entidade: ConflitoEntidade;
  uuid_local: string;
  campo: string;
  valor_local: ValorConflito;
  valor_servidor: ValorConflito;
  estrategia: string;
  campo_sensivel: boolean;
  status: ConflitoStatus;
  valor_final: ValorConflito;
  resolvido_por: ConflitoPessoa | null;
  resolvido_em: string | null;
  territorio: { id: number; nome: string } | null;
  tecnico: ConflitoPessoa;
  dispositivo: { id: number; device_id: string; nome: string } | null;
  criado_em: string;
};

/**
 * O detalhe acrescenta `registro_atual`: o objeto COMPLETO como está hoje no
 * servidor. Não existe equivalente do lado local — o `ConflictLog` guarda só o
 * campo em conflito, não um retrato do registro do aparelho.
 */
export type ConflitoDetalhe = Conflito & {
  registro_atual: Record<string, unknown> | null;
};

// ─── Rótulos ─────────────────────────────────────────────────────────────────

export const ENTIDADE_LABEL: Record<ConflitoEntidade, string> = {
  upf: "UPF",
  member: "Membro da família",
  activity: "Atividade de campo",
};

export const STATUS_LABEL: Record<ConflitoStatus, string> = {
  pendente: "Pendente",
  resolvido_auto: "Resolvido automaticamente",
  resolvido_manual: "Resolvido manualmente",
};

/** Espelha ConflictLog.Estrategia. */
export const ESTRATEGIA_LABEL: Record<string, string> = {
  last_write_wins: "Última escrita prevalece",
  duplicate_rejeitado: "Duplicata rejeitada",
  exclusao_prevalece: "Exclusão do servidor prevalece",
  merge_automatico: "Merge automático",
};

/**
 * Nomes humanos dos caminhos que o motor de sincronização produz.
 *
 * Deliberadamente NÃO replicamos aqui a lista de campos sensíveis do backend
 * (`sync_entities.py::sensitive_paths`): a resposta já traz `campo_sensivel`
 * por conflito, e manter uma segunda lista só criaria chance de divergir.
 */
const CAMPO_LABEL: Record<string, string> = {
  "titular.nome_completo": "Nome do titular",
  "titular.cpf": "CPF do titular",
  nome_completo: "Nome completo",
  cpf: "CPF",
  latitude: "Latitude",
  longitude: "Longitude",
  titulo: "Título",
  descricao: "Descrição",
  whatsapp: "WhatsApp",
  telefone: "Telefone",
};

/** `titular.cpf` vira "CPF do titular"; desconhecidos viram legíveis assim mesmo. */
export function rotuloCampo(campo: string): string {
  const conhecido = CAMPO_LABEL[campo];
  if (conhecido) return conhecido;

  const partes = campo.split(".").map((parte) => parte.replace(/_/g, " "));
  const legivel = partes.join(" › ");
  return legivel.charAt(0).toUpperCase() + legivel.slice(1);
}

/** Texto exibido para um valor do conflito. Nulo e vazio são estados distintos. */
export function formatarValor(valor: ValorConflito): string {
  if (valor === null || valor === undefined) return "(sem valor)";
  if (typeof valor === "boolean") return valor ? "Sim" : "Não";
  if (typeof valor === "number") return String(valor);
  if (typeof valor === "string") return valor.trim() === "" ? "(vazio)" : valor;
  return JSON.stringify(valor);
}

// ─── Edição manual ───────────────────────────────────────────────────────────

/**
 * Converte o texto digitado para o TIPO do valor original.
 *
 * O backend grava o que receber em JSONField, sem coagir: mandar "-8.05" como
 * texto onde havia número gravaria uma string na latitude e o defeito só
 * apareceria muito depois, na próxima sincronização.
 */
export function converterValorManual(
  texto: string,
  referencia: ValorConflito,
): { valor: ValorConflito } | { erro: string } {
  if (typeof referencia === "number") {
    const numero = Number(texto.replace(",", ".").trim());
    if (texto.trim() === "" || Number.isNaN(numero)) {
      return { erro: "Informe um número — este campo é numérico." };
    }
    return { valor: numero };
  }

  if (typeof referencia === "boolean") {
    const normalizado = texto.trim().toLowerCase();
    if (["true", "sim", "1"].includes(normalizado)) return { valor: true };
    if (["false", "não", "nao", "0"].includes(normalizado)) return { valor: false };
    return { erro: "Informe Sim ou Não." };
  }

  if (texto.trim() === "") {
    return { erro: "Informe o valor que deve prevalecer." };
  }
  return { valor: texto };
}

/** Texto inicial do campo de edição manual, a partir de um valor existente. */
export function valorParaTexto(valor: ValorConflito): string {
  if (valor === null || valor === undefined) return "";
  if (typeof valor === "string") return valor;
  if (typeof valor === "number" || typeof valor === "boolean") return String(valor);
  return JSON.stringify(valor);
}

// ─── Leitura e escrita ───────────────────────────────────────────────────────

const CONFLITOS_URL = "/api/v1/sca/conflicts/";

/** Filtros aceitos por ConflictLogFilter. Strings vazias são omitidas. */
export type ConflitoFiltros = {
  status?: string;
  /** "true" | "false" — BooleanFilter do django-filters. */
  campo_sensivel?: string;
  entidade?: string;
};

/** SCAPagination: LimitOffset com 20 por página e teto de 100. */
export const CONFLITOS_POR_PAGINA = 20;

/**
 * GET /api/v1/sca/conflicts/
 *
 * `ordering=status,-criado_em` deixa os pendentes no topo: "pendente" vem antes
 * de "resolvido_auto" e "resolvido_manual" na ordenação alfabética que o backend
 * aplica ao campo.
 */
export async function listConflitos(
  filtros: ConflitoFiltros = {},
  offset = 0,
  signal?: AbortSignal,
): Promise<Paginated<Conflito>> {
  const qs = new URLSearchParams({
    ordering: "status,-criado_em",
    limit: String(CONFLITOS_POR_PAGINA),
  });
  if (offset > 0) qs.set("offset", String(offset));
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor) qs.set(chave, valor);
  }

  const res = await apiClient(`${CONFLITOS_URL}?${qs.toString()}`, { signal });
  return res.json();
}

/** GET /api/v1/sca/conflicts/{id}/ — inclui o registro atual do servidor. */
export async function fetchConflito(
  id: number,
  signal?: AbortSignal,
): Promise<ConflitoDetalhe> {
  const res = await apiClient(`${CONFLITOS_URL}${id}/`, { signal });
  return res.json();
}

/**
 * POST /api/v1/sca/conflicts/{id}/resolver/
 *
 * Aplica o valor escolhido ao registro definitivo, marca `resolvido_manual` e
 * grava auditoria — tudo numa transação do backend. Responde 409 quando o
 * conflito já não está pendente (alguém resolveu antes), o que o `apiClient`
 * converte em `ApiError` com `code: "CONFLITO_JA_RESOLVIDO"`.
 */
export async function resolverConflito(
  id: number,
  decisao: ConflitoDecisao,
  valorManual?: ValorConflito,
): Promise<ConflitoDetalhe> {
  const body: { decisao: ConflitoDecisao; valor_manual?: ValorConflito } = {
    decisao,
  };
  if (decisao === "manual") body.valor_manual = valorManual ?? null;

  const res = await apiClient(`${CONFLITOS_URL}${id}/resolver/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.json();
}
