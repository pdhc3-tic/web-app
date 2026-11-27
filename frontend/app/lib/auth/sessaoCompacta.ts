import type { Perfil, Territorio } from "./types";

/**
 * O que o cookie de sessão guarda do `/auth/me` (#448).
 *
 * O cookie vai e volta em toda requisição ao Next (páginas, prefetches e
 * `/api/auth/session`). Ele guardava o `/auth/me` inteiro, e para os perfis
 * nacionais o backend devolve todos os territórios do projeto: o cookie
 * passava de 16 KB e crescia com o cadastro. Fica só o que o front lê.
 */

/** Do perfil, a sessão só usa estes campos (permissões e o nome no menu). */
export type PerfilDaSessao = Pick<Perfil, "id" | "nome" | "slug" | "categoria">;

/**
 * Perfis de alcance nacional: o `/auth/me` devolve todos os territórios para
 * eles. Quem só tem perfis assim fica sem a lista na sessão; a única tela que a
 * lê para esses perfis (Nova demanda) busca todos quando ela vem vazia.
 */
export const PERFIS_NACIONAIS: readonly string[] = ["super-admin", "ugp", "fgd"];

export function compactarUsuario(me: {
  perfis: (Perfil | PerfilDaSessao)[];
  territorios: Territorio[];
}): { perfis: PerfilDaSessao[]; territorios: Territorio[] } {
  const perfis = (me.perfis ?? []).map(({ id, nome, slug, categoria }) => ({
    id,
    nome,
    slug,
    ...(categoria ? { categoria } : {}),
  }));
  const soNacionais = perfis.length > 0 && perfis.every((p) => PERFIS_NACIONAIS.includes(p.slug));
  const territorios = soNacionais
    ? []
    : (me.territorios ?? []).map(({ id, nome, estados }) => ({ id, nome, estados: estados ?? [] }));
  return { perfis, territorios };
}
