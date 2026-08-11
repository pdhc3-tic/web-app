import path from "node:path";

/**
 * Usuários do `manage.py seed_demo` usados pelos E2E.
 *
 * - `ugp`          → perfil "ugp": escrita liberada no Plano de Trabalho
 *                    (espelha o `IsSuperAdmin | IsUGP` do backend).
 * - `semPermissao` → perfil "adt-acr": lê as Metas, mas não pode criar,
 *                    editar nem excluir.
 */
export type UserKey = "ugp" | "semPermissao";

export const USERS: Record<UserKey, { email: string; password: string }> = {
  ugp: {
    email: process.env.E2E_UGP_EMAIL ?? "beatriz.nogueira@demo.pdhc.local",
    password: process.env.E2E_PASSWORD ?? "Pdhc@2026demo",
  },
  semPermissao: {
    email: process.env.E2E_LEITOR_EMAIL ?? "marina.albuquerque@demo.pdhc.local",
    password: process.env.E2E_PASSWORD ?? "Pdhc@2026demo",
  },
};

/**
 * Caminho do storageState de cada perfil. O login roda uma vez no projeto
 * `setup` — o backend tem rate limit no /auth/login/, então repetir o login a
 * cada teste levaria a 429.
 *
 * Fica fora de `frontend/` pelo mesmo motivo do `outputDir` (ver
 * playwright.config.ts): escrever no diretório observado pelo Next dev
 * recarrega a página no meio do teste.
 */
export function storageStatePath(key: UserKey): string {
  return path.resolve(__dirname, "..", "..", "..", ".playwright", "auth", `${key}.json`);
}
