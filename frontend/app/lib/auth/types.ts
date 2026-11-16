import type { Session } from "next-auth";

export interface Perfil {
  id: number;
  nome: string;
  slug: string;
  descricao: string;
  /**
   * Principal (com território) ou operacional (com objeto de abrangência), do
   * `RoleSerializer` (#405, AJ-BE-10). Opcional: a sessão gravada antes da
   * mudança não traz o campo.
   */
  categoria?: "principal" | "operacional";
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
