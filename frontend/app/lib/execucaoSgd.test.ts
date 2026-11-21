import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchSubmetaOptions } from "./execucaoSgd";

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

/** Submetas de várias Metas, como `GET /sgp/submetas/` sem filtro devolve. */
const todas = Array.from({ length: 250 }, (_, i) => ({
  id: 3000 + i,
  numero: `${(i % 7) + 1}.${Math.floor(i / 7) + 1}`,
  titulo: `Submeta ${i}`,
}));

/** `UFPAPagination`: paginada por `page`, teto de 200 por página. */
function servidor() {
  api.client.mockImplementation(async (caminho: string) => {
    const url = new URL(caminho, "http://local");
    const tamanho = Math.min(Number(url.searchParams.get("page_size") ?? 50), 200);
    const pagina = Number(url.searchParams.get("page") ?? 1);
    const inicio = (pagina - 1) * tamanho;
    return {
      json: async () => ({
        count: todas.length,
        next: inicio + tamanho < todas.length ? "proxima" : null,
        results: todas.slice(inicio, inicio + tamanho),
      }),
    };
  });
}

beforeEach(() => api.client.mockReset());

describe("fetchSubmetaOptions — filtro de Submeta da Execução (revisão do PR #434)", () => {
  it("traz as Submetas além da primeira página, ordenadas pelo número", async () => {
    servidor();
    const opcoes = await fetchSubmetaOptions();

    expect(opcoes).toHaveLength(250);
    expect(opcoes.map((o) => o.value)).toContain("3249");
    expect(api.client).toHaveBeenCalledTimes(2);
    // Ordem numérica: 1.2 antes de 1.10.
    const daMeta1 = opcoes.filter((o) => o.label.startsWith("1.")).map((o) => o.label.split(" — ")[0]);
    expect(daMeta1.indexOf("1.2")).toBeLessThan(daMeta1.indexOf("1.10"));
  });
});
