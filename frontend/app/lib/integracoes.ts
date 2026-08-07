import { ApiError, apiClient } from "@/app/lib/api";

/**
 * Configurações não sensíveis da integração com o Google Calendar.
 *
 * Espelha o endpoint singleton `GoogleCalendarConfigView`
 * (apps/core/views/system_config.py). Por baixo os valores vivem em chaves do
 * SystemConfig, mas isso é detalhe do backend: aqui só existe o payload plano
 * `{ calendario_destino_id, lembretes, integracao_ativa }`.
 *
 * Credenciais OAuth2 NÃO passam por este módulo — ficam em variável de ambiente
 * (`GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO` / `_FILE`) e nunca são expostas pela
 * API. Ver backend/docs/google-calendar.md.
 */

const CONFIG_URL = "/api/v1/core/config/google-calendar/";

// ─── Limites do Google Calendar ──────────────────────────────────────────────
// O backend valida apenas `min_value=1` por lembrete — sem teto e sem limite de
// quantidade. Replicamos os limites reais do Google aqui para o erro aparecer na
// edição, e não silenciosamente na sincronização assíncrona.

/** 4 semanas em minutos — teto de antecedência aceito pelo Google Calendar. */
export const REMINDER_MAX_MINUTES = 40320;
/** Máximo de lembretes por evento no Google Calendar. */
export const REMINDER_MAX_COUNT = 5;

// ─── Tipos ───────────────────────────────────────────────────────────────────

/** Espelha GoogleCalendarConfigSerializer (apps/core/serializers.py). */
export type GoogleCalendarConfig = {
  calendario_destino_id: string;
  /** Minutos de antecedência de cada lembrete. */
  lembretes: number[];
  integracao_ativa: boolean;
};

/** Usado como estado inicial enquanto a requisição não volta. */
export const EMPTY_CONFIG: GoogleCalendarConfig = {
  calendario_destino_id: "",
  lembretes: [],
  integracao_ativa: false,
};

/** Rótulo humano de cada campo, para mensagens de erro do backend. */
export const CONFIG_FIELD_LABEL: Record<keyof GoogleCalendarConfig, string> = {
  calendario_destino_id: "Calendário destino",
  lembretes: "Lembretes",
  integracao_ativa: "Integração ativa",
};

// ─── Leitura e escrita ───────────────────────────────────────────────────────

function normalizeConfig(raw: Partial<GoogleCalendarConfig>): GoogleCalendarConfig {
  return {
    calendario_destino_id:
      typeof raw?.calendario_destino_id === "string"
        ? raw.calendario_destino_id
        : "",
    lembretes: Array.isArray(raw?.lembretes)
      ? raw.lembretes
          .map((v) => Number(v))
          .filter((n) => Number.isInteger(n) && n > 0)
          // O backend semeia [1440, 60]; ordenar deixa a leitura da lista
          // previsível, do lembrete mais próximo ao mais distante.
          .sort((a, b) => a - b)
      : [],
    integracao_ativa: raw?.integracao_ativa === true,
  };
}

/** GET — configuração atual. Lança ApiError (403 para não Super Admin). */
export async function fetchGoogleCalendarConfig(
  signal?: AbortSignal,
): Promise<GoogleCalendarConfig> {
  const res = await apiClient(CONFIG_URL, { signal });
  return normalizeConfig(await res.json());
}

/**
 * PATCH — grava a configuração e devolve o estado persistido.
 *
 * A view é `@transaction.atomic`: ou os três campos gravam, ou nenhum. Não há
 * estado parcial a tratar, então o erro pode subir para quem chama.
 */
export async function saveGoogleCalendarConfig(
  config: GoogleCalendarConfig,
): Promise<GoogleCalendarConfig> {
  const res = await apiClient(CONFIG_URL, {
    method: "PATCH",
    body: JSON.stringify({
      calendario_destino_id: config.calendario_destino_id.trim(),
      lembretes: config.lembretes,
      integracao_ativa: config.integracao_ativa,
    }),
  });
  return normalizeConfig(await res.json());
}

/** Compara dois estados para habilitar o botão Salvar. */
export function configEquals(
  a: GoogleCalendarConfig,
  b: GoogleCalendarConfig,
): boolean {
  return (
    a.calendario_destino_id.trim() === b.calendario_destino_id.trim() &&
    a.integracao_ativa === b.integracao_ativa &&
    a.lembretes.length === b.lembretes.length &&
    a.lembretes.every((v, i) => v === b.lembretes[i])
  );
}

// ─── Status de sincronização ─────────────────────────────────────────────────

/**
 * `pendente` está na lista porque é o vocabulário que o backend já usa em
 * `Activity.google_calendar_sync_status` (ok/pendente/erro) — é provável que o
 * endpoint agregado espelhe esses mesmos valores. `indisponivel` é local: marca
 * "não consegui falar com o endpoint", nunca vem do servidor.
 */
export type SyncEstado =
  | "ok"
  | "pendente"
  | "erro"
  | "nunca_executada"
  | "indisponivel";

export type GoogleCalendarStatus = {
  estado: SyncEstado;
  ultimaSincronizacao: string | null;
  ultimoErro: string | null;
  falhasRecentes: number;
};

const STATUS_INDISPONIVEL: GoogleCalendarStatus = {
  estado: "indisponivel",
  ultimaSincronizacao: null,
  ultimoErro: null,
  falhasRecentes: 0,
};

type RawStatus = {
  estado?: string;
  ultima_sincronizacao?: string | null;
  ultimo_erro?: string | null;
  falhas_recentes?: number;
};

/** Estados que podem vir do servidor. `indisponivel` é sempre local. */
const ESTADOS_DO_SERVIDOR: SyncEstado[] = [
  "ok",
  "pendente",
  "erro",
  "nunca_executada",
];

const STATUS_URL = `${CONFIG_URL}status/`;

/**
 * Avisa no console quando o endpoint responde mas fora do contrato.
 *
 * Sem isto a divergência é invisível: o fallback devolve `indisponivel` e a tela
 * fica idêntica à de quando o endpoint ainda não existia — dando a impressão de
 * que o backend não entregou, quando na verdade entregou diferente.
 */
function avisarContratoDivergente(motivo: string, recebido: unknown): void {
  console.warn(
    `[google-calendar] ${STATUS_URL} respondeu fora do contrato: ${motivo}. ` +
      "Esperado { estado: 'ok'|'pendente'|'erro'|'nunca_executada', " +
      "ultima_sincronizacao, ultimo_erro, falhas_recentes }. Recebido:",
    recebido,
  );
}

/**
 * GET /api/v1/core/config/google-calendar/status/
 *
 * **Este endpoint ainda não existe.** O backend rastreia a sincronização por
 * atividade (`Activity.google_calendar_sync_status`), sem visão agregada da
 * integração — não há "última sincronização" nem contagem de falhas em lugar
 * nenhum, e o campo por atividade nem é filtrável no ActivityFilter.
 *
 * A função já consome o contrato pedido ao time do backend. Nunca lança:
 * 404 é o estado esperado hoje e passa calado; qualquer outra divergência
 * avisa no console para não passar despercebida.
 */
export async function fetchGoogleCalendarStatus(
  signal?: AbortSignal,
): Promise<GoogleCalendarStatus> {
  let raw: RawStatus;

  try {
    const res = await apiClient(STATUS_URL, { signal });
    raw = (await res.json()) as RawStatus;
  } catch (e) {
    // 404 = endpoint ainda não implementado. É o estado normal hoje, sem ruído.
    if (e instanceof ApiError && e.status === 404) return STATUS_INDISPONIVEL;
    // Abort não é erro: a tela foi desmontada no meio da requisição.
    if (signal?.aborted) return STATUS_INDISPONIVEL;
    avisarContratoDivergente(
      e instanceof ApiError ? `HTTP ${e.status}` : "falha de rede",
      e,
    );
    return STATUS_INDISPONIVEL;
  }

  if (!raw || typeof raw !== "object") {
    avisarContratoDivergente("corpo não é um objeto", raw);
    return STATUS_INDISPONIVEL;
  }

  if (!ESTADOS_DO_SERVIDOR.includes(raw.estado as SyncEstado)) {
    avisarContratoDivergente(`estado desconhecido '${raw.estado}'`, raw);
    return STATUS_INDISPONIVEL;
  }

  // O estado é válido, mas um campo pode ter vindo com outro nome — o caso mais
  // traiçoeiro, porque a tela exibiria "nunca executada" com confiança.
  // Só vale para 'ok' e 'erro': em 'pendente' (primeira sincronização em curso)
  // e 'nunca_executada' a ausência da data é legítima.
  if (
    (raw.estado === "ok" || raw.estado === "erro") &&
    !raw.ultima_sincronizacao
  ) {
    avisarContratoDivergente(
      `estado '${raw.estado}' sem 'ultima_sincronizacao'`,
      raw,
    );
  }

  return {
    estado: raw.estado as SyncEstado,
    ultimaSincronizacao: raw.ultima_sincronizacao ?? null,
    ultimoErro: raw.ultimo_erro ?? null,
    falhasRecentes:
      typeof raw.falhas_recentes === "number" ? raw.falhas_recentes : 0,
  };
}

// ─── Validação dos lembretes ─────────────────────────────────────────────────

/** Erro de validação ao adicionar um lembrete, ou null quando válido. */
export function validateReminder(
  minutos: number,
  existentes: number[],
): string | null {
  if (!Number.isInteger(minutos) || minutos <= 0) {
    return "Informe um número inteiro de minutos maior que zero.";
  }
  if (minutos > REMINDER_MAX_MINUTES) {
    return `O Google Calendar aceita no máximo ${REMINDER_MAX_MINUTES} minutos (4 semanas).`;
  }
  if (existentes.includes(minutos)) {
    return "Este lembrete já foi adicionado.";
  }
  if (existentes.length >= REMINDER_MAX_COUNT) {
    return `Máximo de ${REMINDER_MAX_COUNT} lembretes por evento.`;
  }
  return null;
}

/** 1440 → "1 dia antes". Usado ao lado de cada chip de lembrete. */
export function formatReminder(minutos: number): string {
  if (minutos < 60) {
    return `${minutos} min antes`;
  }
  if (minutos < 1440) {
    const horas = minutos / 60;
    const label = Number.isInteger(horas) ? String(horas) : horas.toFixed(1);
    return `${label} ${horas === 1 ? "hora" : "horas"} antes`;
  }
  const dias = minutos / 1440;
  const label = Number.isInteger(dias) ? String(dias) : dias.toFixed(1);
  return `${label} ${dias === 1 ? "dia" : "dias"} antes`;
}
