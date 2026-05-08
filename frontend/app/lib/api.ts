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

async function parseApiError(res: Response): Promise<never> {
  try {
    const body: ApiErrorBody = await res.json();
    throw new ApiError(res.status, body);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(res.status, {
      code: "unknown_error",
      message: `Erro inesperado (${res.status})`,
    });
  }
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
