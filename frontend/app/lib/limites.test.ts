import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  comRotulo,
  dataVizinha,
  hojeIso,
  precedenciaDo,
  sobrealocacaoDoErro,
} from "./limites";

describe("comRotulo (#400): nome do período que o backend devolveu", () => {
  it("trimestral e semestral pela posição do início no ano", () => {
    expect(comRotulo({ inicio: "2026-10-01", fim: "2026-12-31", periodicidade: "trimestral" }).rotulo).toBe(
      "4º trimestre de 2026",
    );
    expect(comRotulo({ inicio: "2026-07-01", fim: "2026-12-31", periodicidade: "semestral" }).rotulo).toBe(
      "2º semestre de 2026",
    );
  });

  it("mensal e vigência", () => {
    expect(comRotulo({ inicio: "2028-02-01", fim: "2028-02-29", periodicidade: "mensal" }).rotulo).toBe("fev/2028");
    expect(comRotulo({ inicio: "2000-01-01", fim: "2099-12-31", periodicidade: "vigencia" }).rotulo).toBe(
      "Vigência do TED",
    );
  });

  it("mantém as datas do backend", () => {
    expect(comRotulo({ inicio: "2026-01-01", fim: "2026-03-31", periodicidade: "trimestral" })).toMatchObject({
      inicio: "2026-01-01",
      fim: "2026-03-31",
    });
  });
});

describe("dataVizinha", () => {
  it("anda um dia para fora do período, virando o ano", () => {
    const q1 = comRotulo({ inicio: "2026-01-01", fim: "2026-03-31", periodicidade: "trimestral" });
    expect(dataVizinha(q1, -1)).toBe("2025-12-31");
    expect(dataVizinha(q1, 1)).toBe("2026-04-01");
  });
});

it("hojeIso usa a data local", () => {
  expect(hojeIso(new Date(2026, 10, 9, 23, 30))).toBe("2026-11-09");
});

describe("precedenciaDo", () => {
  it("padrão, herdado e sobrescrito", () => {
    expect(precedenciaDo({ escopo: "perfil", herdado: false })).toBe("padrao");
    expect(precedenciaDo({ escopo: "individual", herdado: true })).toBe("herdado");
    expect(precedenciaDo({ escopo: "individual", herdado: false })).toBe("sobrescrito");
  });
});

describe("sobrealocacaoDoErro", () => {
  const erro = (raw: unknown) =>
    new ApiError(400, { code: "validation_error", message: "Dados inválidos." }, raw);

  it("lê a soma e o pool do 400 de exigir_dentro_do_pool", () => {
    const raw = {
      valor_limite: "A soma dos limites do território (R$ 12.000,00) passa do pool (R$ 10.000,00), e a sobrealocação está desligada.",
      soma_limites: "12000.00",
      valor_pool: "10000.00",
      territorio: "3",
    };
    expect(sobrealocacaoDoErro(erro(raw))).toEqual({
      somaLimites: "12000.00",
      valorPool: "10000.00",
      mensagem: raw.valor_limite,
    });
  });

  it("aceita os valores em lista, como o DRF devolve às vezes", () => {
    expect(sobrealocacaoDoErro(erro({ soma_limites: ["1.00"], valor_pool: ["0.50"] }))).toMatchObject({
      somaLimites: "1.00",
      valorPool: "0.50",
    });
  });

  it("outro erro não é sobrealocação", () => {
    expect(sobrealocacaoDoErro(erro({ justificativa: ["Obrigatória."] }))).toBeNull();
    expect(sobrealocacaoDoErro(new Error("x"))).toBeNull();
  });
});
