import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Constantes ─────────────────────────────────────────────────────────────

/**
 * Unidades de medida da Ação — espelha apps/sgp/constants.py::TIPO_UNIDADE_MEDIDA.
 *
 * Diferente das demais listas do SGP, esta NÃO é servida por
 * GET /api/v1/choices/ (a SGPChoicesView não a expõe). Como é lista fechada e
 * curta, espelhá-la aqui evita um endpoint novo — mesmo critério já aplicado
 * aos ODS em metas.ts.
 */
export const TIPO_UNIDADE_OPTIONS: SelectOption[] = [
  { value: "1", label: "Seminário" },
  { value: "2", label: "Oficina" },
  { value: "3", label: "Curso / Capacitação" },
  { value: "4", label: "Plano" },
  { value: "5", label: "Relatório de pesquisas" },
  { value: "6", label: "Intercâmbio" },
  { value: "7", label: "Conteúdo audiovisual" },
  { value: "8", label: "Visita técnica" },
  { value: "9", label: "Encontro / Reunião" },
  { value: "10", label: "Unidade implementada" },
  { value: "11", label: "Família atendida" },
  { value: "12", label: "Outro" },
];

/**
 * Formato do número da Ação: X.Y (1.1, 2.3, 10.2).
 *
 * Mesma regex do backend — validate_numero_acao no model e validate_numero no
 * serializer. Validar aqui só antecipa a resposta; quem manda continua sendo o
 * servidor, que também checa a unicidade dentro da Meta.
 */
export const NUMERO_ACAO_RE = /^\d+\.\d+$/;

// ─── Status de execução ─────────────────────────────────────────────────────

/** Valores de WorkPlanAcao.status_execucao. */
export type AcaoStatus = "no_prazo" | "em_atraso" | "concluida";

const STATUS_LABEL: Record<AcaoStatus, string> = {
  no_prazo: "No prazo",
  em_atraso: "Em atraso",
  concluida: "Concluída",
};

export function acaoStatusLabel(status: string): string {
  return STATUS_LABEL[status as AcaoStatus] ?? status;
}

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/sgp/serializers_workplan.py::WorkPlanAcaoSerializer. */
export type Acao = {
  id: number;
  meta: number;
  numero: string;
  descricao: string;
  tipo_unidade: number;
  tipo_unidade_display: string;
  /** DecimalField → string no DRF. */
  quantidade_planejada: string;
  valor_unitario: string;
  /** Derivado: quantidade_planejada × valor_unitario. */
  valor_total: string;
  /**
   * Derivado: contagem de Atividades de Campo com status "concluido"
   * vinculadas à Ação. NÃO soma quantidades — ver progressoAcao().
   */
  quantidade_realizada: string;
  data_inicio: string | null;
  data_fim: string | null;
  status_execucao: AcaoStatus;
  criado_em?: string;
  atualizado_em?: string;
};

/** Campos graváveis (os demais são read_only no serializer). */
export type AcaoWritePayload = {
  meta: number;
  numero: string;
  descricao: string;
  tipo_unidade: number;
  quantidade_planejada: string;
  valor_unitario: string;
  data_inicio: string | null;
  data_fim: string | null;
};

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
 */
export function progressoAcao(acao: Acao): Progresso {
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
export function progressoLabel(acao: Acao): string {
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
