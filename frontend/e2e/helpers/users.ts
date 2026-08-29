import path from "node:path";

/**
 * Usuários do `manage.py seed_demo` usados pelos E2E.
 *
 * - `ugp`          → perfil "ugp": escrita liberada no Plano de Trabalho
 *                    (espelha o `IsSuperAdmin | IsUGP` do backend).
 * - `semPermissao` → perfil "adt-acr": lê as Metas, mas não pode criar,
 *                    editar nem excluir.
 * - `articuladorPE` / `articuladorPB` → perfil "articulador-estadual", cada um
 *                    vinculado a um conjunto DISJUNTO de territórios (PE/AL/MA e
 *                    PB/RN/BA/MG). O par existe para provar o recorte por estado:
 *                    um não pode enxergar os conflitos do outro.
 * - `superAdmin`   → perfil "super-admin" com território nulo (acesso global).
 *                    É o único que entra nas telas de /admin. Atenção: tanto o
 *                    `IsSuperAdmin` do backend quanto o `isSuperAdmin()` do
 *                    front checam o PERFIL de slug "super-admin" — a flag
 *                    `is_superuser` de um `createsuperuser` não serve.
 */
export type UserKey =
  | "ugp"
  | "semPermissao"
  | "articuladorPE"
  | "articuladorPB"
  | "superAdmin";

export const USERS: Record<UserKey, { email: string; password: string }> = {
  ugp: {
    email: process.env.E2E_UGP_EMAIL ?? "beatriz.nogueira@demo.pdhc.local",
    password: process.env.E2E_PASSWORD ?? "Pdhc@2026demo",
  },
  semPermissao: {
    email: process.env.E2E_LEITOR_EMAIL ?? "marina.albuquerque@demo.pdhc.local",
    password: process.env.E2E_PASSWORD ?? "Pdhc@2026demo",
  },
  articuladorPE: {
    email: process.env.E2E_ARTICULADOR_PE_EMAIL ?? "sandra.queiroz@demo.pdhc.local",
    password: process.env.E2E_PASSWORD ?? "Pdhc@2026demo",
  },
  articuladorPB: {
    email: process.env.E2E_ARTICULADOR_PB_EMAIL ?? "helio.fontenele@demo.pdhc.local",
    password: process.env.E2E_PASSWORD ?? "Pdhc@2026demo",
  },
  superAdmin: {
    email: process.env.E2E_SUPER_ADMIN_EMAIL ?? "vera.lucena@demo.pdhc.local",
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
