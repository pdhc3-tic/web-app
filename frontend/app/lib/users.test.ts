import { describe, expect, it, vi } from "vitest";
import { listUsers, perfisDaListagem, type UserListItem } from "./users";

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

type PerfilDaLista = UserListItem["perfis"][number];

const perfil = (parcial: Partial<PerfilDaLista>): PerfilDaLista =>
  ({ id: 1, nome: "Gestor", slug: "gestor", categoria: "principal", ...parcial }) as PerfilDaLista;

describe("listUsers (#405)", () => {
  it("faz uma só consulta, com a página e o perfil pedidos ao servidor", async () => {
    api.client.mockReset();
    api.client.mockResolvedValue({ json: async () => ({ count: 0, next: null, previous: null, results: [] }) });

    await listUsers({ limit: 20, offset: 40, perfil: "7", search: " Ana " });

    expect(api.client).toHaveBeenCalledTimes(1);
    const url = new URL(api.client.mock.calls[0][0], "http://local");
    expect(url.searchParams.get("limit")).toBe("20");
    expect(url.searchParams.get("offset")).toBe("40");
    expect(url.searchParams.get("perfil")).toBe("7");
    expect(url.searchParams.get("search")).toBe("Ana");
    // A categoria não vai: o backend ainda não filtra por ela (pendência 3).
    expect(url.searchParams.has("categoria")).toBe(false);
  });
});

describe("perfisDaListagem (#405)", () => {
  it("junta o principal repetido por território e mostra o objeto do operacional", () => {
    const itens = perfisDaListagem([
      perfil({ id: 1, nome: "Articulador Estadual" }),
      perfil({ id: 1, nome: "Articulador Estadual" }),
      perfil({ id: 5, nome: "Coordenador de evento", slug: "coordenador-evento", categoria: "operacional", objeto_tipo: "evento", objeto_id: 12 }),
      perfil({ id: 5, nome: "Coordenador de evento", slug: "coordenador-evento", categoria: "operacional", objeto_tipo: "evento", objeto_id: 30 }),
    ]);

    expect(itens.map((i) => i.rotulo)).toEqual([
      "Articulador Estadual",
      "Coordenador de evento · evento 12",
      "Coordenador de evento · evento 30",
    ]);
    expect(new Set(itens.map((i) => i.chave)).size).toBe(3);
  });

  it("operacional sem objeto mostra só o nome", () => {
    const [item] = perfisDaListagem([perfil({ id: 5, nome: "Credenciador", categoria: "operacional" })]);
    expect(item.rotulo).toBe("Credenciador");
  });
});
