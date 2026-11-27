import { describe, expect, it, vi } from "vitest";
import { canVerHistoricoRemanejamentos } from "@/app/lib/auth/roles";
import {
  TRANSFERENCIAS_POR_PAGINA,
  listTransferencias,
  nomeDoPoolDoRemanejamento,
  origemDaTransferencia,
  queryTransferencias,
} from "@/app/lib/remanejamentos";

/**
 * #466 — histórico de remanejamentos: a consulta à listagem de transferências,
 * a origem de cada remanejamento e quem pode ver a tela.
 */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/api")>("@/app/lib/api");
  return { ...atual, apiClient: api.client };
});

describe("queryTransferencias", () => {
  it("sem filtro, só o tamanho da página; a primeira página não manda offset", () => {
    expect(queryTransferencias({ limit: TRANSFERENCIAS_POR_PAGINA, offset: 0 }).toString()).toBe("limit=20");
  });

  it("rubrica pelo slug e o deslocamento da página", () => {
    expect(queryTransferencias({ rubrica: "diarias", limit: 50, offset: 100 }).toString()).toBe(
      "rubrica=diarias&limit=50&offset=100",
    );
  });
});

describe("listTransferencias", () => {
  it("GET em /sgd/remanejamentos/transferencias/ e devolve a página com o total", async () => {
    api.client.mockResolvedValue({ json: async () => ({ count: 42, results: [{ id: 7 }] }) });
    const r = await listTransferencias({ rubrica: "diarias", limit: 20, offset: 20 });
    expect(api.client.mock.calls.at(-1)?.[0]).toBe(
      "/api/v1/sgd/remanejamentos/transferencias/?rubrica=diarias&limit=20&offset=20",
    );
    expect(r).toEqual({ transferencias: [{ id: 7 }], total: 42 });
  });
});

describe("origemDaTransferencia", () => {
  it("escopo vazio: remanejamento direto da UGP, sem link", () => {
    expect(origemDaTransferencia({ escopo: "", demanda_id: null, pedido: null })).toEqual({
      rotulo: "Direto da UGP",
      href: null,
    });
  });

  it("pontual: excedente autorizado na demanda, com link para a demanda", () => {
    expect(origemDaTransferencia({ escopo: "pontual", demanda_id: "41", pedido: null })).toEqual({
      rotulo: "Excedente da demanda #41",
      href: "/sgd/demandas?demanda=41",
    });
  });

  it("elevação de limite: recurso extra, com link para o pedido", () => {
    expect(origemDaTransferencia({ escopo: "elevacao_limite", demanda_id: "41", pedido: 9 })).toEqual({
      rotulo: "Recurso extra (pedido #9)",
      href: "/sgd/remanejamentos/9",
    });
  });
});

describe("nomeDoPoolDoRemanejamento", () => {
  it.each([
    [{ id: 1, nivel: "territorial", estado: null, territorio: "Sertão do Pajeú" }, "Sertão do Pajeú"],
    [{ id: 2, nivel: "estadual", estado: "PE", territorio: null }, "PE"],
    [{ id: 3, nivel: "nacional", estado: null, territorio: null }, "Nacional"],
  ] as const)("%o → %s", (pool, nome) => {
    expect(nomeDoPoolDoRemanejamento(pool)).toBe(nome);
  });
});

describe("canVerHistoricoRemanejamentos", () => {
  const com = (...slugs: string[]) => ({ perfis: slugs.map((slug) => ({ slug })) }) as never;

  it.each([
    ["ugp", true],
    ["super-admin", true],
    ["fgd", true],
    ["articulador-estadual", false],
    ["adt-acr", false],
  ])("%s: %s", (slug, pode) => {
    expect(canVerHistoricoRemanejamentos(com(slug))).toBe(pode);
  });

  it("sem sessão, não", () => {
    expect(canVerHistoricoRemanejamentos(null)).toBe(false);
  });
});
