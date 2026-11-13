import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import {
  confirmarRemanejamento,
  mensagemDeErro,
  simularRemanejamento,
} from "@/app/lib/remanejamentoSgp";

/**
 * #402 — contrato do cliente de simulação e confirmação de remanejamento.
 */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/api")>("@/app/lib/api");
  return { ...atual, apiClient: api.client };
});

function ultimaChamada() {
  return api.client.mock.calls.at(-1) as [string, RequestInit];
}

function responder(corpo: unknown) {
  api.client.mockResolvedValue({ json: async () => corpo });
}

const payload = {
  origem_allocation: 10,
  destino_allocation: 20,
  valor: "1000.00",
  justificativa: "Realocação da rubrica",
};

describe("simularRemanejamento", () => {
  it("POST em /orcamento/remanejamentos/simular/ com o payload", async () => {
    responder({ origem: {}, destino: {} });
    await simularRemanejamento(payload);
    const [path, init] = ultimaChamada();
    expect(path).toBe("/api/v1/sgp/orcamento/remanejamentos/simular/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });
});

describe("confirmarRemanejamento", () => {
  it("POST em /orcamento/remanejamentos/ com o mesmo payload simulado", async () => {
    responder([{ id: 1 }]);
    await confirmarRemanejamento(payload);
    const [path, init] = ultimaChamada();
    expect(path).toBe("/api/v1/sgp/orcamento/remanejamentos/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });
});

describe("mensagemDeErro", () => {
  /** O 400 de `_exigir_saldo_na_origem`, como o `apiClient` o entrega. */
  const recusa = (corpo: Record<string, unknown>) =>
    new ApiError(400, { code: "INSUFFICIENT_BALANCE", message: "Saldo insuficiente na origem: R$ 200.00 disponível." }, corpo);

  it("na simulação, INSUFFICIENT_BALANCE diz que o valor passa do saldo, com o saldo formatado", () => {
    const msg = mensagemDeErro(recusa({ code: "INSUFFICIENT_BALANCE", disponivel: "1200.50" }), "simular");
    expect(msg).toMatch(/^O valor passa do saldo da origem: há R\$\s1\.200,50 disponível para remanejar\.$/);
  });

  it("na confirmação, INSUFFICIENT_BALANCE diz que o saldo mudou e pede nova simulação", () => {
    const msg = mensagemDeErro(recusa({ code: "INSUFFICIENT_BALANCE", disponivel: "200.00" }), "confirmar");
    expect(msg).toMatch(/^O saldo da origem mudou desde a simulação e agora é R\$\s200,00\. Simule de novo/);
    expect(msg).not.toContain("INSUFFICIENT_BALANCE");
  });

  it("sem o saldo no corpo, as mensagens ficam sem o valor", () => {
    expect(mensagemDeErro(recusa({}), "simular")).toBe("O valor passa do saldo da origem.");
    expect(mensagemDeErro(recusa({}), "confirmar")).toBe(
      "O saldo da origem mudou desde a simulação. Simule de novo antes de confirmar.",
    );
  });

  it("demais códigos repassam a message do backend", () => {
    const erro = new ApiError(400, {
      code: "VALIDATION_ERROR",
      message: "Origem e destino devem ser da mesma rubrica.",
    });
    expect(mensagemDeErro(erro, "simular")).toBe("Origem e destino devem ser da mesma rubrica.");
  });

  it("erro genérico sem ApiError vira o texto da etapa", () => {
    expect(mensagemDeErro(new Error("fail"), "simular")).toBe("Não foi possível simular o remanejamento.");
    expect(mensagemDeErro(new Error("fail"), "confirmar")).toBe(
      "Não foi possível concluir o remanejamento.",
    );
  });
});
