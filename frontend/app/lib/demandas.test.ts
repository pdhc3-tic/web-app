import { describe, expect, it, vi } from "vitest";
import { listDemandas, listRiscosDeGlosaDaAtividade, riscosAbertos } from "@/app/lib/demandas";

/**
 * #364 — a listagem master-detail passa a ordenação pelo servidor
 * (`?ordering=`), nunca somando as solicitações no cliente.
 */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

describe("riscos da atividade (#404)", () => {
  it("pede uma página de 100 da atividade, sem percorrer as demais", async () => {
    api.client.mockReset();
    api.client.mockResolvedValueOnce({ json: async () => ({
      next: "http://backend/glosa-riscos/?offset=100",
      results: [{ id: 1, resolvido_em: "2026-11-10" }, { id: 2, resolvido_em: null }],
    }) });
    const resultado = await listRiscosDeGlosaDaAtividade(42);
    expect(api.client).toHaveBeenCalledTimes(1);
    const url = new URL(api.client.mock.calls[0][0], "http://local");
    expect(url.pathname).toBe("/api/v1/sgp/glosa-riscos/");
    expect(url.searchParams.get("activity")).toBe("42");
    expect(url.searchParams.get("limit")).toBe("100");
    expect(riscosAbertos(resultado).map((r) => r.id)).toEqual([2]);
  });
});

function urlDaChamada(): URL {
  const chamada = api.client.mock.calls.at(-1)?.[0] as string;
  return new URL(chamada, "http://local");
}

function responder(corpo: unknown = { count: 0, results: [] }) {
  api.client.mockResolvedValue({ json: async () => corpo });
}

describe("listDemandas — ordenação pelo servidor (#364)", () => {
  it("sem ordenação não envia `ordering`, deixando o padrão do backend", async () => {
    responder();
    await listDemandas();
    expect(urlDaChamada().searchParams.has("ordering")).toBe(false);
  });

  it("asc envia `ordering=valor_estimado_total`", async () => {
    responder();
    await listDemandas({ ordenacao: "valor_estimado_total" });
    expect(urlDaChamada().searchParams.get("ordering")).toBe("valor_estimado_total");
  });

  it("desc envia `ordering=-valor_estimado_total`", async () => {
    responder();
    await listDemandas({ ordenacao: "-valor_estimado_total" });
    expect(urlDaChamada().searchParams.get("ordering")).toBe("-valor_estimado_total");
  });

  it("preserva os demais parâmetros", async () => {
    responder();
    await listDemandas({
      aguardandoMinhaAcao: true,
      filtros: { atividade: "42" },
      ordenacao: "-valor_estimado_total",
      pagina: { offset: 50, limit: 50 },
    });
    const qs = urlDaChamada().searchParams;
    expect(qs.get("aguardando_minha_acao")).toBe("true");
    expect(qs.get("atividade")).toBe("42");
    expect(qs.get("ordering")).toBe("-valor_estimado_total");
    expect(qs.get("limit")).toBe("50");
    expect(qs.get("offset")).toBe("50");
  });
});
