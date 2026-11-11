import { describe, expect, it, vi } from "vitest";
import { listUsers, type UserListItem } from "./users";

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

describe("listUsers por categoria (#405)", () => {
  it("filtra todas as páginas antes de contar e paginar, incluindo usuários com duas categorias", async () => {
    const usuario = (id: number, categorias: string[]) => ({
      id, perfis: categorias.map((categoria) => ({ categoria })),
    }) as UserListItem;
    api.client.mockReset();
    api.client.mockResolvedValueOnce({ json: async () => ({
      next: "http://backend/users/?offset=2", results: [usuario(1, ["principal"]), usuario(2, ["operacional"])],
    }) });
    api.client.mockResolvedValueOnce({ json: async () => ({
      next: null, results: [usuario(3, ["principal", "operacional"])],
    }) });
    const resultado = await listUsers({ categoria: "operacional", offset: 1, limit: 1, search: "Ana" });
    expect(resultado.count).toBe(2);
    expect(resultado.results.map((u) => u.id)).toEqual([3]);
    const segunda = new URL(api.client.mock.calls[1][0], "http://local");
    expect(segunda.searchParams.get("offset")).toBe("2");
    expect(segunda.searchParams.get("search")).toBe("Ana");
  });
});
