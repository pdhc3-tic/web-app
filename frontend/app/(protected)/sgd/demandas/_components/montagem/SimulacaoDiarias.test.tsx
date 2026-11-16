import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { SimulacaoDiarias as Simulacao } from "@/app/lib/solicitacoes";
import { SimulacaoDiarias, useSimulacaoDiarias } from "./SimulacaoDiarias";

/**
 * #366 — pré-visualização das diárias no formulário: faixa, valor unitário,
 * quantidade (com meia diária) e total, vindos de `/sgd/config/diarias/simular/`.
 */

const api = vi.hoisted(() => ({ simular: vi.fn() }));

vi.mock("@/app/lib/solicitacoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/solicitacoes")>()),
  simularDiarias: api.simular,
}));

type Viagem = { municipio: string; ida: string; volta: string; hospedagemCusteada?: boolean };

function Quadro({ municipio, ida, volta, hospedagemCusteada }: Viagem) {
  return <SimulacaoDiarias {...useSimulacaoDiarias(municipio, ida, volta, hospedagemCusteada)} />;
}

function montar(viagem: Viagem) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const arvore = (v: Viagem) => (
    <QueryClientProvider client={client}>
      <Quadro {...v} />
    </QueryClientProvider>
  );
  const { rerender } = render(arvore(viagem));
  return { mudar: (v: Viagem) => rerender(arvore(v)) };
}

function simulacao(numero: string, total: string, extra: Partial<Simulacao> = {}): Simulacao {
  return {
    faixa_destino: { id: 3, nome: "Demais localidades" },
    valor_por_diaria: "300.00",
    numero_diarias: numero,
    adicional_embarque: "0.00",
    valor_total: total,
    ...extra,
  };
}

const texto = (testId: string) => screen.getByTestId(testId).textContent ?? "";

// Com chaves: o `beforeEach` trata função devolvida como limpeza e chamaria o mock.
beforeEach(() => {
  api.simular.mockReset();
});

describe("SimulacaoDiarias (#366)", () => {
  it("viagem no mesmo dia: meia diária, no singular", async () => {
    api.simular.mockResolvedValue(simulacao("0.5", "150.00"));
    montar({ municipio: "12", ida: "2026-11-16", volta: "2026-11-16" });

    await screen.findByTestId("simulacao-diarias-resultado");
    expect(api.simular).toHaveBeenCalledWith(
      { municipioDestinoId: "12", dataInicio: "2026-11-16", dataFim: "2026-11-16", hospedagemCusteada: false },
      expect.anything(),
    );
    expect(texto("simulacao-diarias-resultado")).toContain("Demais localidades");
    expect(texto("simulacao-diarias-resultado")).toContain("300,00");
    expect(texto("simulacao-diarias-quantidade")).toBe("0,5 diária");
    expect(texto("simulacao-diarias-total")).toContain("150,00");
  });

  it("viagem com pernoites: pernoites inteiros e meia diária no retorno", async () => {
    api.simular.mockResolvedValue(simulacao("2.5", "750.00"));
    montar({ municipio: "12", ida: "2026-11-16", volta: "2026-11-18" });

    await screen.findByTestId("simulacao-diarias-resultado");
    expect(texto("simulacao-diarias-quantidade")).toBe("2,5 diárias");
    expect(texto("simulacao-diarias-total")).toContain("750,00");
    expect(screen.queryByTestId("simulacao-diarias-adicional")).toBeNull();
  });

  it("marcar hospedagem custeada consulta de novo e recalcula", async () => {
    api.simular.mockImplementation(async (p: { hospedagemCusteada?: boolean }) =>
      p.hospedagemCusteada ? simulacao("1.5", "450.00") : simulacao("2.5", "750.00"),
    );
    const { mudar } = montar({ municipio: "12", ida: "2026-11-16", volta: "2026-11-18" });
    await waitFor(() => expect(texto("simulacao-diarias-quantidade")).toBe("2,5 diárias"));

    mudar({ municipio: "12", ida: "2026-11-16", volta: "2026-11-18", hospedagemCusteada: true });

    await waitFor(() => expect(texto("simulacao-diarias-quantidade")).toBe("1,5 diárias"));
    expect(texto("simulacao-diarias-total")).toContain("450,00");
    expect(api.simular).toHaveBeenLastCalledWith(
      expect.objectContaining({ hospedagemCusteada: true }),
      expect.anything(),
    );
  });

  it("mostra o adicional de embarque e desembarque quando ele entra no total", async () => {
    api.simular.mockResolvedValue(simulacao("2.5", "845.00", { adicional_embarque: "95.00" }));
    montar({ municipio: "12", ida: "2026-11-16", volta: "2026-11-18" });

    expect((await screen.findByTestId("simulacao-diarias-adicional")).textContent).toContain("95,00");
    expect(texto("simulacao-diarias-total")).toContain("845,00");
  });

  it("sem valor vigente, mostra a mensagem do backend", async () => {
    const mensagem = "Sem valor de diária vigente para a faixa 'Demais localidades' em 16/11/2026. Contate a FGD ou o Super Admin.";
    api.simular.mockRejectedValue(new ApiError(400, { code: "error", message: mensagem }));
    montar({ municipio: "12", ida: "2026-11-16", volta: "2026-11-18" });

    expect((await screen.findByTestId("simulacao-diarias-erro")).textContent).toContain(mensagem);
    expect(screen.queryByTestId("simulacao-diarias-resultado")).toBeNull();
  });

  it("sem destino ou datas, não consulta o backend", () => {
    montar({ municipio: "", ida: "2026-11-16", volta: "" });

    expect(screen.getByTestId("simulacao-diarias").textContent).toContain("Preencha o destino e as datas");
    expect(api.simular).not.toHaveBeenCalled();
  });
});
