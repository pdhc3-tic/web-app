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
  it("INSUFFICIENT_BALANCE pede nova simulação", () => {
    const erro = new ApiError(400, {
      code: "INSUFFICIENT_BALANCE",
      message: "Saldo insuficiente",
    });
    expect(mensagemDeErro(erro)).toBe(
      "O saldo mudou entre a simulação e a confirmação (INSUFFICIENT_BALANCE). Simule de novo antes de confirmar.",
    );
  });

  it("demais códigos repassam a message do backend", () => {
    const erro = new ApiError(400, {
      code: "VALIDATION_ERROR",
      message: "Valor inválido.",
    });
    expect(mensagemDeErro(erro)).toBe("Valor inválido.");
  });

  it("erro genérico sem ApiError vira texto padrão", () => {
    expect(mensagemDeErro(new Error("fail"))).toBe(
      "Não foi possível concluir o remanejamento.",
    );
  });
});
