import { apiClient } from "@/app/lib/api";
import type { Acao, AcaoStatus } from "@/app/lib/acoes";
import type { Paginated } from "@/app/lib/users";

/**
 * Camada de dados do Painel de Acompanhamento (FE-9).
 *
 * O semáforo e os indicadores vêm PRONTOS do backend, por
 * `GET /api/v1/sgp/plano-trabalho/painel/` (Issue #136). A tela não recalcula
 * nada: a regra de classificação mora em
 * `apps/sgp/services/workplan_dashboard.py::_semaphore` e é a mesma que dispara
 * o alerta diário de Ações vermelhas — duas implementações discordariam, e o
 * gestor veria uma cor na tela e outra no e-mail.
 *
 * O endpoint agrega e filtra, mas devolve só o necessário ao cálculo. Faltam
 * campos descritivos que a tela exibe (`tipo_unidade_display`, valores, datas
 * da Meta), por isso `listMetas()` e `listTodasAcoes()` continuam sendo
 * carregados UMA VEZ e cruzados por id. São ≤7 Metas e ≤100 Ações; a troca de
 * filtro refaz apenas a chamada do painel. Ver as sugestões abertas com a
 * equipe do backend para eliminar esse cruzamento.
 */

// ─── Contrato do endpoint ───────────────────────────────────────────────────

/** Níveis que o backend produz. `sem-dado` é decisão da UI — ver semaforo.ts. */
export type SemaforoApi = "verde" | "amarelo" | "vermelho";

/** Meta enxuta do painel: WorkPlanDashboardMetaSerializer. */
export type PainelMetaApi = {
  id: number;
  numero: number;
  titulo: string;
};

/** Espelha apps/sgp/serializers_workplan.py::WorkPlanDashboardAcaoSerializer. */
export type PainelAcaoApi = {
  id: number;
  meta: PainelMetaApi;
  numero: string;
  descricao: string;
  /** DecimalField → string no DRF, como no resto da API. */
  quantidade_planejada: string;
  /** CONTAGEM de Atividades concluídas — mesma semântica de acoes.ts. */
  quantidade_realizada: string;
  /** 0–100. Sem teto: uma Ação pode passar de 100%. */
  percentual_realizado: string;
  /** 0–100: fração do período já decorrida, com as datas herdadas da Meta. */
  progresso_esperado: string;
  semaforo: SemaforoApi;
  status_execucao: AcaoStatus;
  /** Datas próprias da Ação — nulas quando o cálculo herdou as da Meta. */
  data_inicio: string | null;
  data_fim: string | null;
};

/** Contagem por nível que o backend já devolve por Meta. */
export type PainelResumoApi = {
  total_acoes: number;
  verde: number;
  amarelo: number;
  vermelho: number;
};

export type PainelMetaGrupoApi = {
  meta: PainelMetaApi;
  resumo: PainelResumoApi;
  acoes: PainelAcaoApi[];
};

export type PainelResponse = {
  metas: PainelMetaGrupoApi[];
};

/** Filtros aceitos por WorkPlanDashboardQuerySerializer. */
export type PainelFiltrosApi = {
  meta_id?: string;
  territorio_id?: string;
  status_execucao?: string;
};

const PAINEL_PATH = "/api/v1/sgp/plano-trabalho/painel/";

/**
 * GET /api/v1/sgp/plano-trabalho/painel/
 *
 * Sem paginação: o endpoint devolve o Plano de Trabalho inteiro já agrupado por
 * Meta. Chaves vazias são omitidas — o backend valida os valores e rejeitaria
 * uma string vazia como inteiro.
 */
export async function fetchPainel(
  filtros: PainelFiltrosApi = {},
  signal?: AbortSignal,
): Promise<PainelResponse> {
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

// ─── Campos descritivos ─────────────────────────────────────────────────────

/**
 * GET /api/v1/acoes/ — todas as Ações, sem filtro de Meta.
 *
 * Serve apenas ao cruzamento descritivo: `tipo_unidade_display`,
 * `valor_unitario` e `valor_total` não existem na resposta do painel. Os
 * números que alimentam o semáforo vêm sempre do endpoint do painel.
 */
export async function listTodasAcoes(signal?: AbortSignal): Promise<Acao[]> {
  const res = await apiClient("/api/v1/acoes/?page_size=100&ordering=numero", {
    signal,
  });
  const data: Paginated<Acao> = await res.json();
  return data.results;
}
