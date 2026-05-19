import type { Session } from "next-auth";

export interface Perfil {
  id: number;
  nome: string;
  slug: string;
  descricao: string;
  ativo: boolean;
  criado_em: string;
}

export interface Territorio {
  id: number;
  nome: string;
  estados: string[];
}

/** Shape do usuário autenticado exposto pelo useSession() — sem tokens. */
export type User = Session["user"];
