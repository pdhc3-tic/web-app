import { describe, expect, it, vi } from "vitest";
import { alvoDoAlerta, escopoDoAlerta, fetchAlertas, nivelDoAlerta } from "@/app/lib/alertasOrcamento";

/** #403: cliente e leitura dos alertas orçamentários. */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

function qsDaChamada(): URLSearchParams {
  const url = new URL(api.client.mock.calls.at(-1)?.[0] as string, "http://local");
  expect(url.pathname).toBe("/api/v1/sgp/orcamento/alertas/");
  return url.searchParams;
}

describe("fetchAlertas", () => {
  it("pede só os abertos e não envia filtro vazio", async () => {
    api.client.mockResolvedValue({ json: async () => ({ count: 0, results: [] }) });
    await fetchAlertas({ tipo: "", faixa: "" });
    const qs = qsDaChamada();
    expect(qs.get("abertos")).toBe("true");
    expect(qs.get("limit")).toBe("10");
    expect(qs.has("tipo")).toBe(false);
    expect(qs.has("faixa")).toBe(false);
  });

  it("envia tipo, faixa e paginação quando informados", async () => {
    api.client.mockResolvedValue({ json: async () => ({ count: 0, results: [] }) });
    await fetchAlertas({ tipo: "subexecucao", faixa: "devolucao", limit: 20, offset: 20 });
    const qs = qsDaChamada();
    expect(qs.get("tipo")).toBe("subexecucao");
    expect(qs.get("faixa")).toBe("devolucao");
    expect(qs.get("limit")).toBe("20");
    expect(qs.get("offset")).toBe("20");
  });
});

describe("nivelDoAlerta", () => {
  it("vermelho e devolução são críticos; amarelo e subexecução pedem atenção", () => {
    expect(nivelDoAlerta({ faixa: "vermelho" })).toBe("vermelho");
    expect(nivelDoAlerta({ faixa: "devolucao" })).toBe("vermelho");
    expect(nivelDoAlerta({ faixa: "amarelo" })).toBe("amarelo");
    expect(nivelDoAlerta({ faixa: "subexecucao" })).toBe("amarelo");
  });

  it("sem faixa fica neutro", () => {
    expect(nivelDoAlerta({ faixa: "" })).toBe("sem-dado");
  });
});

const alvo = (parcial: Partial<NonNullable<Parameters<typeof alvoDoAlerta>[0]["alvo"]>>) => ({
  nome: null,
  nivel: null,
  estado: null,
  territorio: null,
  usuario: null,
  ...parcial,
});

describe("alvoDoAlerta (#423, item 5)", () => {
  it("usa o nome que o backend devolve, com a rubrica", () => {
    expect(
      alvoDoAlerta({
        escopo: "pool",
        referencia_id: 7,
        rubrica_nome: "Diárias",
        alvo: alvo({ nome: "Cariri Paraibano", nivel: "territorial", territorio: { id: 2, nome: "Cariri Paraibano" } }),
      }),
    ).toBe("Cariri Paraibano · Diárias");
    expect(
      alvoDoAlerta({
        escopo: "limite",
        referencia_id: 9,
        rubrica_nome: "Diárias",
        alvo: alvo({ nome: "Ana Souza", usuario: { id: 4, nome: "Ana Souza" } }),
      }),
    ).toBe("Ana Souza · Diárias");
  });

  it("sem nome, cai no escopo com a rubrica ou o id", () => {
    expect(alvoDoAlerta({ escopo: "pool", referencia_id: 7, rubrica_nome: "Diárias", alvo: null })).toBe(
      "Pool · Diárias",
    );
    expect(alvoDoAlerta({ escopo: "meta", referencia_id: 3, rubrica_nome: null, alvo: null })).toBe("Meta #3");
  });
});

describe("escopoDoAlerta", () => {
  it("dá o nível do pool e o nome do escopo nos demais", () => {
    expect(escopoDoAlerta({ escopo: "pool", alvo: alvo({ nome: "Nacional", nivel: "nacional" }) })).toBe(
      "Pool nacional",
    );
    expect(escopoDoAlerta({ escopo: "pool", alvo: null })).toBe("Pool");
    expect(escopoDoAlerta({ escopo: "limite", alvo: alvo({ nome: "Ana Souza" }) })).toBe("Limite de gasto");
  });
});
