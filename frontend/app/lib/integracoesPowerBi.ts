import { ApiError, apiClient } from "@/app/lib/api";

/**
 * Painel administrativo da integração Power BI (#143).
 *
 * O endpoint público (`/api/v1/sgp/plano-trabalho/powerbi/`) é o que a
 * ferramenta Power BI consome — ele já existe (`WorkPlanPowerBIView`,
 * `backend/apps/sgp/urls.py:82`). O que **não existe ainda** é o endpoint
 * ADMIN que esta tela consome — para ver/mascarar/regerar o token de
 * serviço. As chamadas abaixo estão prontas para o dia em que o backend
 * subir o endpoint; enquanto isso, um 404 vira `PowerBiPendenteError` e
 * a tela mostra um aviso claro em vez de um erro genérico.
 *
 * Contrato esperado (a alinhar com o backend — está em
 * `frontend/docs/pendencias-backend-sprint-8.md`, item 3):
 *
 *   GET  /api/v1/admin/power-bi-token/            → PowerBiConfig
 *   POST /api/v1/admin/power-bi-token/regenerar/  → PowerBiTokenRegenerado
 */

/** Erro sentinel para "endpoint admin ainda não implementado". */
export class PowerBiPendenteError extends Error {
  constructor() {
    super(
      "O endpoint de administração do token Power BI ainda não está " +
        "disponível — aguardando implementação no backend.",
    );
    this.name = "PowerBiPendenteError";
  }
}

/**
 * Estado atual da integração. `token_mascarado` deve vir com o mesmo
 * formato exibido: ex.: `••••••3f2a` (últimos 4 caracteres visíveis).
 * `atualizado_em` é o timestamp do último `refresh_power_bi_snapshot`
 * bem-sucedido — permite exibir "há X min" e o indicador de atraso
 * (verde/vermelho) se passou muito do intervalo esperado.
 */
export type PowerBiConfig = {
  /**
   * URL pública do endpoint consumido pelo Power BI. Preencher com a URL
   * absoluta (ex.: `https://app.exemplo.com.br/api/v1/sgp/plano-trabalho/powerbi/`)
   * ou relativa — a tela apenas exibe.
   */
  url_endpoint: string;
  /** Token mascarado para exibição (ex.: `••••••3f2a`). Nunca o valor cru. */
  token_mascarado: string;
  /**
   * Timestamp ISO do último snapshot atualizado com sucesso. `null` quando
   * o backend nunca gerou o snapshot (integração recém-configurada).
   */
  atualizado_em: string | null;
};

/** Resposta da regeneração. `novo_token` é EXIBIDO UMA ÚNICA VEZ. */
export type PowerBiTokenRegenerado = {
  novo_token: string;
};

const ADMIN_TOKEN_PATH = "/api/v1/admin/power-bi-token/";
const ADMIN_REGENERAR_PATH = "/api/v1/admin/power-bi-token/regenerar/";

/** GET /api/v1/admin/power-bi-token/ — lê o estado atual. */
export async function fetchPowerBiConfig(
  signal?: AbortSignal,
): Promise<PowerBiConfig> {
  try {
    const res = await apiClient(ADMIN_TOKEN_PATH, { signal });
    return res.json();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      throw new PowerBiPendenteError();
    }
    throw e;
  }
}

/**
 * POST /api/v1/admin/power-bi-token/regenerar/ — gera novo token e invalida
 * o anterior. Retorna o novo token EM CLARO — a tela o exibe uma única vez
 * (não pode ser recuperado depois).
 */
export async function regenerarPowerBiToken(): Promise<PowerBiTokenRegenerado> {
  try {
    const res = await apiClient(ADMIN_REGENERAR_PATH, {
      method: "POST",
    });
    return res.json();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      throw new PowerBiPendenteError();
    }
    throw e;
  }
}
