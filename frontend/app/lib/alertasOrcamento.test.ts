import { describe, expect, it, vi } from "vitest";
import { alvoDoAlerta, fetchAlertas, nivelDoAlerta } from "@/app/lib/alertasOrcamento";

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

describe("alvoDoAlerta", () => {
  it("usa a rubrica quando há, e o id do alvo quando não há", () => {
    expect(alvoDoAlerta({ escopo: "pool", referencia_id: 7, rubrica_nome: "Diárias" })).toBe("Pool · Diárias");
    expect(alvoDoAlerta({ escopo: "meta", referencia_id: 3, rubrica_nome: null })).toBe("Meta #3");
  });
});
