import { getSession, signIn, signOut } from "next-auth/react";
import type { Session } from "next-auth";

// --- Tipos de erro padronizados ---

export interface ApiFieldError {
  field: string;
  message: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  field_errors?: ApiFieldError[];
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors?: ApiFieldError[];

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.fieldErrors = body.field_errors;
  }
}

/**
 * Normaliza o corpo de erro em ApiErrorBody. Aceita três formatos:
 * 1. Envelope da API `{ code, message, field_errors? }` (usado como está);
 * 2. `{ detail: "..." }` do DRF → vira `message`;
 * 3. Erros de validação DRF `{ campo: ["msg"] | "msg", ... }` → `field_errors`
 *    (a chave `non_field_errors` é tratada como erro global, sem `field`).
 */
function normalizeErrorBody(status: number, raw: unknown): ApiErrorBody {
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;

    if (typeof obj.message === "string") {
      return raw as ApiErrorBody;
    }
    if (typeof obj.detail === "string") {
      return {
        code: typeof obj.code === "string" ? obj.code : "error",
        message: obj.detail,
      };
    }

    const fieldErrors: ApiFieldError[] = [];
    let firstMessage: string | undefined;
    let globalMessage: string | undefined;

    for (const [field, value] of Object.entries(obj)) {
      const message = Array.isArray(value)
        ? String(value[0])
        : typeof value === "string"
          ? value
          : JSON.stringify(value);
      firstMessage ??= message;
      if (field === "non_field_errors" || field === "detail") {
        globalMessage ??= message;
      } else {
        fieldErrors.push({ field, message });
      }
    }

    if (fieldErrors.length > 0 || globalMessage) {
      return {
        code: "validation_error",
        message: globalMessage ?? firstMessage ?? "Dados inválidos.",
        field_errors: fieldErrors.length > 0 ? fieldErrors : undefined,
      };
    }
  }

  return { code: "unknown_error", message: `Erro inesperado (${status})` };
}

async function parseApiError(res: Response): Promise<never> {
  let raw: unknown = null;
  try {
    raw = await res.json();
  } catch {
    /* corpo vazio ou não-JSON */
  }
  throw new ApiError(res.status, normalizeErrorBody(res.status, raw));
}

// --- Utilitários internos ---

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function buildHeaders(token: string, extra?: HeadersInit): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(extra as Record<string, string>),
  };
}

// Deduplicação: enquanto um refresh estiver em curso, demais requisições
// concorrentes aguardam a mesma promise em vez de cada uma disparar getSession().
let refreshPromise: Promise<Session | null> | null = null;

function getRefreshedSession(): Promise<Session | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = getSession().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

/**
 * Fetch autenticado para uso em Client Components.
 * Injeta o Bearer token da sessão Auth.js e intercepta respostas 401,
 * tentando renovar o token automaticamente antes de repetir a requisição.
 * Requisições concorrentes que recebem 401 compartilham um único refresh.
 */
export async function apiClient(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const session = await getSession();

  if (!session?.accessToken) {
    signIn();
    throw new ApiError(401, { code: "invalid_session", message: "Sessão inválida." });
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: buildHeaders(session.accessToken, options.headers),
  });

  if (res.status !== 401) {
    if (!res.ok) await parseApiError(res);
    return res;
  }

  // Token expirado — aguarda o refresh compartilhado (next-auth faz a renovação)
  const refreshed = await getRefreshedSession();

  if (!refreshed?.accessToken || refreshed.error === "RefreshTokenExpired") {
    const next =
      typeof window !== "undefined"
        ? window.location.pathname + window.location.search
        : "/";
    await signOut({ redirectTo: `/login?next=${encodeURIComponent(next)}` });
    throw new ApiError(401, { code: "session_expired", message: "Sessão expirada." });
  }

  // Retry com o token renovado
  const retried = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: buildHeaders(refreshed.accessToken, options.headers),
  });

  if (!retried.ok) await parseApiError(retried);
  return retried;
}

// --- Logout ---

export async function logout(): Promise<void> {
  const session = await getSession();
  if (session?.accessToken && session?.refreshToken) {
    // Usa fetch direto para evitar loop infinito caso o backend retorne 401
    await fetch(`${BASE_URL}/api/v1/auth/logout/`, {
      method: "POST",
      headers: buildHeaders(session.accessToken),
      body: JSON.stringify({ refresh_token: session.refreshToken }),
    }).catch(() => {});
  }
  await signOut({ redirectTo: "/login" });
}
