import { apiClient } from "@/app/lib/api";

/**
 * Painel administrativo da integração Power BI (#143).
 *
 * São dois endpoints de papéis bem diferentes:
 *
 * - `/api/v1/sgp/plano-trabalho/powerbi/` é o endpoint PÚBLICO que a
 *   ferramenta Power BI consome, autenticado pelo token de serviço
 *   (`PowerBIServiceTokenAuthentication`). Esta tela só exibe a URL dele.
 * - `/api/v1/admin/power-bi-token/` é o endpoint ADMIN que esta tela
 *   consome, restrito a Super Admin (`PowerBITokenView`,
 *   apps/core/views/power_bi_token.py).
 *
 * O valor em claro do token só existe no retorno da regeneração: o banco
 * guarda apenas o SHA-256 e a versão mascarada (`PowerBIToken.gerar`), então
 * não há como a tela recuperá-lo depois — daí o diálogo de exibição única.
 */

/** Status do snapshot calculado pelo servidor, com limite de 1h (AC-2). */
export type StatusSnapshot = "sem_snapshot" | "em_dia" | "atrasado";

const STATUS_SNAPSHOT: StatusSnapshot[] = ["sem_snapshot", "em_dia", "atrasado"];

/** Espelha PowerBITokenStatusSerializer (apps/core/serializers.py). */
export type PowerBiConfig = {
  /** URL do endpoint público consumido pelo Power BI. A tela apenas exibe. */
  url_endpoint: string;
  /**
   * Token mascarado (`••••3f2a`, últimos 4 caracteres). `null` quando nunca
   * se gerou nenhum token — estado inicial de qualquer ambiente novo, já que
   * o `seed_demo` não cria `PowerBIToken`.
   */
  token_mascarado: string | null;
  /**
   * ISO do último `refresh_power_bi_snapshot` bem-sucedido, ou `null` se o
   * snapshot nunca foi gerado.
   */
  atualizado_em: string | null;
  /**
   * `null` quando a resposta não traz o campo (ou traz valor desconhecido) —
   * aí a tela recai no cálculo local. Fora isso, o servidor é a fonte de
   * verdade: ele aplica o mesmo limite de 1h, mas com o relógio dele.
   */
  status_snapshot: StatusSnapshot | null;
};

/**
 * Espelha PowerBITokenRegenerateSerializer. `token` é o valor EM CLARO e
 * chega uma única vez — o nome do campo é `token`, e não `novo_token` como
 * chegou a ser pedido ao backend.
 */
export type PowerBiTokenRegenerado = {
  token: string;
  token_mascarado: string;
  criado_em: string;
};

const ADMIN_TOKEN_PATH = "/api/v1/admin/power-bi-token/";
const ADMIN_REGENERAR_PATH = "/api/v1/admin/power-bi-token/regenerar/";

function normalizeConfig(raw: Partial<PowerBiConfig>): PowerBiConfig {
  const status = raw?.status_snapshot;
  return {
    url_endpoint:
      typeof raw?.url_endpoint === "string" ? raw.url_endpoint : "",
    // Campo anulável no serializer: `""` também vale como "não existe token".
    token_mascarado: raw?.token_mascarado ? raw.token_mascarado : null,
    atualizado_em: raw?.atualizado_em ?? null,
    status_snapshot: STATUS_SNAPSHOT.includes(status as StatusSnapshot)
      ? (status as StatusSnapshot)
      : null,
  };
}

/** GET — estado atual. Lança ApiError (403 para quem não é Super Admin). */
export async function fetchPowerBiConfig(
  signal?: AbortSignal,
): Promise<PowerBiConfig> {
  const res = await apiClient(ADMIN_TOKEN_PATH, { signal });
  return normalizeConfig(await res.json());
}

/**
 * POST — invalida o token ativo e emite outro, na mesma transação
 * (`PowerBIToken.gerar`). O retorno traz o valor em claro; quem chama é
 * responsável por exibi-lo uma única vez e não persistir em lugar nenhum.
 */
export async function regenerarPowerBiToken(): Promise<PowerBiTokenRegenerado> {
  const res = await apiClient(ADMIN_REGENERAR_PATH, { method: "POST" });
  return res.json();
}
