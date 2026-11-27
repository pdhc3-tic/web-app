import { describe, expect, it } from "vitest";
import { compactarUsuario } from "./sessaoCompacta";
import type { Perfil, Territorio } from "./types";

/** #448: o cookie guarda só o que o front lê, e sem todos os territórios dos perfis nacionais. */

function perfil(slug: string): Perfil {
  return {
    id: slug.length,
    nome: slug.toUpperCase(),
    slug,
    descricao: "Texto longo que o front não usa.",
    categoria: "principal",
    ativo: true,
    criado_em: "2026-01-01T00:00:00Z",
  };
}

const territorios = Array.from({ length: 150 }, (_, i) => ({
  id: i + 1,
  nome: `Território ${i + 1}`,
  estados: ["PE"],
  articulador: 7,
  ativo: true,
})) as unknown as Territorio[];

describe("compactarUsuario (#448)", () => {
  it("perfil só com id, nome, slug e categoria", () => {
    expect(compactarUsuario({ perfis: [perfil("adt-acr")], territorios: [] }).perfis).toEqual([
      { id: 7, nome: "ADT-ACR", slug: "adt-acr", categoria: "principal" },
    ]);
  });

  it("território só com id, nome e estados", () => {
    expect(compactarUsuario({ perfis: [perfil("adt-acr")], territorios: territorios.slice(0, 1) }).territorios).toEqual([
      { id: 1, nome: "Território 1", estados: ["PE"] },
    ]);
  });

  it.each(["ugp", "fgd", "super-admin"])("perfil nacional (%s): sem a lista de territórios", (slug) => {
    expect(compactarUsuario({ perfis: [perfil(slug)], territorios }).territorios).toEqual([]);
  });

  it("nacional junto de um perfil com território: mantém os territórios dele", () => {
    const r = compactarUsuario({ perfis: [perfil("ugp"), perfil("articulador-estadual")], territorios: territorios.slice(0, 2) });
    expect(r.territorios.map((t) => t.id)).toEqual([1, 2]);
  });

  it("o tamanho deixa de crescer com os territórios para o perfil nacional", () => {
    const antes = JSON.stringify({ perfis: [perfil("ugp")], territorios }).length;
    const depois = JSON.stringify(compactarUsuario({ perfis: [perfil("ugp")], territorios })).length;
    expect(antes).toBeGreaterThan(10_000);
    expect(depois).toBeLessThan(200);
  });
});
