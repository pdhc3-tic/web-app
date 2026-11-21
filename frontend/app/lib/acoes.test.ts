import { beforeEach, describe, expect, it, vi } from "vitest";
import { listSubmetasDaMeta } from "./acoes";
import { proximoNumeroDeSubmeta } from "./submetas";

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

/** Submetas 7.1 a 7.N, como o backend as guarda. */
const submetas = (n: number) => Array.from({ length: n }, (_, i) => ({ id: 500 + i, numero: `7.${i + 1}` }));

/**
 * O backend de verdade (`UFPAPagination`): paginado por `page`, com teto de
 * página. Aqui o teto é 100, para provar que a função não depende de caber
 * tudo numa página só.
 */
function servidor(todas: { id: number; numero: string }[], teto = 100) {
  api.client.mockImplementation(async (caminho: string) => {
    const url = new URL(caminho, "http://local");
    const tamanho = Math.min(Number(url.searchParams.get("page_size") ?? 50), teto);
    const pagina = Number(url.searchParams.get("page") ?? 1);
    const inicio = (pagina - 1) * tamanho;
    const results = todas.slice(inicio, inicio + tamanho);
    return {
      json: async () => ({
        count: todas.length,
        next: inicio + tamanho < todas.length ? `http://backend/api/v1/sgp/submetas/?page=${pagina + 1}` : null,
        previous: null,
        results,
      }),
    };
  });
}

beforeEach(() => api.client.mockReset());

describe("listSubmetasDaMeta (revisão do PR #434)", () => {
  it("segue as páginas até o fim: a 101ª Submeta vem junto", async () => {
    const todas = submetas(101);
    servidor(todas);

    const lidas = await listSubmetasDaMeta(9);

    expect(lidas).toHaveLength(101);
    expect(lidas.map((s) => s.numero)).toContain("7.101");
    expect(api.client).toHaveBeenCalledTimes(2);
    const urls = api.client.mock.calls.map(([c]) => new URL(c as string, "http://local"));
    expect(urls.map((u) => u.searchParams.get("page"))).toEqual(["1", "2"]);
    expect(urls.every((u) => u.searchParams.get("meta") === "9")).toBe(true);
  });

  it("uma página só quando cabe tudo nela", async () => {
    servidor(submetas(3));
    expect(await listSubmetasDaMeta(9)).toHaveLength(3);
    expect(api.client).toHaveBeenCalledTimes(1);
  });

  it("registro repetido entre páginas entra uma vez", async () => {
    const todas = submetas(3);
    api.client
      .mockResolvedValueOnce({ json: async () => ({ count: 3, next: "x", previous: null, results: todas.slice(0, 2) }) })
      .mockResolvedValueOnce({ json: async () => ({ count: 3, next: null, previous: null, results: todas.slice(1, 3) }) });
    expect((await listSubmetasDaMeta(9)).map((s) => s.numero)).toEqual(["7.1", "7.2", "7.3"]);
  });

  it("com a lista inteira, o próximo número passa do 100: 7.102 depois de 7.101", async () => {
    servidor(submetas(101));
    expect(proximoNumeroDeSubmeta(7, await listSubmetasDaMeta(9))).toBe("7.102");
  });
});
