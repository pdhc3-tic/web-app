import { apiClient } from "@/app/lib/api";

/**
 * Configurações não sensíveis da integração com o Google Calendar.
 *
 * Persistidas como chaves do SystemConfig (apps/core/models/system_config.py),
 * onde `valor` é sempre TextField — a conversão de/para os tipos da UI acontece
 * aqui. Credenciais OAuth2 NÃO passam por este módulo: ficam em variável de
 * ambiente no backend e nunca são expostas pela API.
 *
 * Estado atual: as chaves ainda não foram semeadas no banco e o endpoint de
 * status não existe (BE-4 pendente). Tudo aqui degrada para defaults em vez de
 * lançar, e passa a funcionar sozinho quando o backend entregar sua parte.
 */

// ─── Chaves ──────────────────────────────────────────────────────────────────

export const GCAL_CALENDAR_ID = "gcal_calendar_id";
export const GCAL_REMINDERS = "gcal_reminders";
export const GCAL_ENABLED = "gcal_enabled";

/** As únicas chaves que esta tela lê ou escreve. */
export const GCAL_KEYS = [
  GCAL_CALENDAR_ID,
  GCAL_REMINDERS,
  GCAL_ENABLED,
] as const;

export type GcalKey = (typeof GCAL_KEYS)[number];

/** Rótulo humano de cada chave, usado nas mensagens de erro de salvamento. */
export const GCAL_KEY_LABEL: Record<GcalKey, string> = {
  [GCAL_CALENDAR_ID]: "Calendário destino",
  [GCAL_REMINDERS]: "Lembretes",
  [GCAL_ENABLED]: "Integração ativa",
};

// ─── Limites do Google Calendar ──────────────────────────────────────────────
// Replicados aqui para o erro aparecer na edição, e não só na sincronização.

/** 4 semanas em minutos — teto de antecedência aceito pelo Google Calendar. */
export const REMINDER_MAX_MINUTES = 40320;
/** Máximo de lembretes por evento no Google Calendar. */
export const REMINDER_MAX_COUNT = 5;

// ─── Tipos ───────────────────────────────────────────────────────────────────

export type GoogleCalendarConfig = {
  calendarId: string;
  /** Minutos de antecedência de cada lembrete. */
  reminders: number[];
  enabled: boolean;
};

export type GoogleCalendarConfigResult = {
  config: GoogleCalendarConfig;
  /**
   * false quando alguma das três chaves não existe no backend — a integração
   * ainda não foi provisionada e salvar vai falhar com 404.
   */
  configurado: boolean;
  /** Chaves ausentes, para a UI dizer exatamente o que falta. */
  chavesAusentes: GcalKey[];
};

export const DEFAULT_CONFIG: GoogleCalendarConfig = {
  calendarId: "",
  reminders: [],
  enabled: false,
};

/** Espelha SystemConfigSerializer. */
type SystemConfigItem = {
  chave: string;
  valor: string;
  tipo: string;
  descricao: string;
  atualizado_por: string | null;
  atualizado_em: string;
};

type Envelope<T> = { count?: number; results?: T[] };

// ─── Leitura ─────────────────────────────────────────────────────────────────

function parseReminders(raw: string): number[] {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((v) => Number(v))
      .filter((n) => Number.isInteger(n) && n > 0);
  } catch {
    return [];
  }
}

/** O backend serializa boolean como "True"/"False" (str(bool) do Python). */
function parseBoolean(raw: string): boolean {
  return ["true", "1"].includes(raw.trim().toLowerCase());
}

/**
 * GET /api/v1/system-config/ — lê apenas as três chaves do Google Calendar.
 *
 * Filtrar aqui é deliberado: a listagem devolve TODAS as configurações do
 * sistema, e nada além destas três deve chegar à tela.
 */
export async function fetchGoogleCalendarConfig(
  signal?: AbortSignal,
): Promise<GoogleCalendarConfigResult> {
  const res = await apiClient("/api/v1/system-config/?limit=200", { signal });
  const data = (await res.json()) as
    | SystemConfigItem[]
    | Envelope<SystemConfigItem>;
  const items = Array.isArray(data) ? data : (data.results ?? []);

  const porChave = new Map<string, SystemConfigItem>();
  for (const item of items) {
    if ((GCAL_KEYS as readonly string[]).includes(item.chave)) {
      porChave.set(item.chave, item);
    }
  }

  const chavesAusentes = GCAL_KEYS.filter((k) => !porChave.has(k));

  return {
    config: {
      calendarId: porChave.get(GCAL_CALENDAR_ID)?.valor ?? DEFAULT_CONFIG.calendarId,
      reminders: porChave.has(GCAL_REMINDERS)
        ? parseReminders(porChave.get(GCAL_REMINDERS)!.valor)
        : DEFAULT_CONFIG.reminders,
      enabled: porChave.has(GCAL_ENABLED)
        ? parseBoolean(porChave.get(GCAL_ENABLED)!.valor)
        : DEFAULT_CONFIG.enabled,
    },
    configurado: chavesAusentes.length === 0,
    chavesAusentes: [...chavesAusentes],
  };
}

// ─── Escrita ─────────────────────────────────────────────────────────────────

/** Serializa cada campo para o formato que o SystemConfigSerializer aceita. */
function serializeValor(key: GcalKey, config: GoogleCalendarConfig): string {
  switch (key) {
    case GCAL_CALENDAR_ID:
      return config.calendarId.trim();
    case GCAL_REMINDERS:
      return JSON.stringify(config.reminders);
    case GCAL_ENABLED:
      return String(config.enabled);
  }
}

/** Quais chaves mudaram entre dois estados — evita PATCH desnecessário. */
export function diffConfig(
  original: GoogleCalendarConfig,
  atual: GoogleCalendarConfig,
): GcalKey[] {
  const mudou: GcalKey[] = [];
  if (original.calendarId.trim() !== atual.calendarId.trim()) {
    mudou.push(GCAL_CALENDAR_ID);
  }
  if (
    original.reminders.length !== atual.reminders.length ||
    original.reminders.some((v, i) => v !== atual.reminders[i])
  ) {
    mudou.push(GCAL_REMINDERS);
  }
  if (original.enabled !== atual.enabled) mudou.push(GCAL_ENABLED);
  return mudou;
}

export type SaveResult = {
  salvas: GcalKey[];
  falhas: { key: GcalKey; message: string }[];
};

/**
 * Salva a configuração com um PATCH por chave alterada.
 *
 * O SystemConfig não tem escrita em lote, então não há atomicidade: as três
 * chaves podem falhar independentemente. Duas decisões por causa disso —
 * só enviamos o que mudou (reduz a chance de estado parcial), e usamos
 * allSettled para que uma falha não descarte os sucessos. Quem chama precisa
 * informar ao usuário exatamente o que não salvou.
 */
export async function saveGoogleCalendarConfig(
  original: GoogleCalendarConfig,
  atual: GoogleCalendarConfig,
): Promise<SaveResult> {
  const alteradas = diffConfig(original, atual);
  if (alteradas.length === 0) return { salvas: [], falhas: [] };

  const resultados = await Promise.allSettled(
    alteradas.map((key) =>
      apiClient(`/api/v1/system-config/${key}/`, {
        method: "PATCH",
        body: JSON.stringify({ valor: serializeValor(key, atual) }),
      }),
    ),
  );

  const salvas: GcalKey[] = [];
  const falhas: SaveResult["falhas"] = [];

  resultados.forEach((r, i) => {
    const key = alteradas[i];
    if (r.status === "fulfilled") {
      salvas.push(key);
    } else {
      const reason = r.reason as unknown;
      falhas.push({
        key,
        message:
          reason instanceof Error ? reason.message : "Falha ao salvar.",
      });
    }
  });

  return { salvas, falhas };
}

// ─── Status de sincronização ─────────────────────────────────────────────────

export type SyncEstado = "ok" | "erro" | "nunca_executada" | "indisponivel";

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

const ESTADOS_VALIDOS: SyncEstado[] = ["ok", "erro", "nunca_executada"];

/**
 * GET /api/v1/integrations/google-calendar/status/
 *
 * O endpoint ainda não existe (BE-4 pendente): 404, erro de rede ou payload
 * inesperado devolvem `indisponivel`, que a tela trata como estado normal e não
 * como falha. Nunca lança.
 */
export async function fetchGoogleCalendarStatus(
  signal?: AbortSignal,
): Promise<GoogleCalendarStatus> {
  try {
    const res = await apiClient(
      "/api/v1/integrations/google-calendar/status/",
      { signal },
    );
    const raw = (await res.json()) as RawStatus;

    const estado = ESTADOS_VALIDOS.includes(raw?.estado as SyncEstado)
      ? (raw.estado as SyncEstado)
      : "indisponivel";

    return {
      estado,
      ultimaSincronizacao: raw?.ultima_sincronizacao ?? null,
      ultimoErro: raw?.ultimo_erro ?? null,
      falhasRecentes:
        typeof raw?.falhas_recentes === "number" ? raw.falhas_recentes : 0,
    };
  } catch {
    return STATUS_INDISPONIVEL;
  }
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

/** "1440" → "1 dia antes". Usado ao lado de cada chip de lembrete. */
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
