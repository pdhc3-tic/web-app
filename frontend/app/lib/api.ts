import "server-only";
import { auth } from "@/auth";
import { redirect } from "next/navigation";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Fetch autenticado para uso em Server Components e Server Actions.
 * Injeta automaticamente o Bearer token da sessão Auth.js.
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const session = await auth();

  if (!session?.accessToken) {
    redirect("/login");
  }

  return fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      ...(options.headers as Record<string, string>),
    },
  });
}
