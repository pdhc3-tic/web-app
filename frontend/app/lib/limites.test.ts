import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  dataVizinha,
  hojeIso,
  paraPeriodicidade,
  periodoDe,
  precedenciaDo,
  sobrealocacaoDoErro,
} from "./limites";

describe("periodoDe (#400, espelho de periodo_de)", () => {
  it("trimestral: blocos de três meses a partir de janeiro", () => {
    expect(periodoDe("2026-11-10", "trimestral")).toEqual({
      inicio: "2026-10-01",
      fim: "2026-12-31",
      rotulo: "4º trimestre de 2026",
    });
    expect(periodoDe("2026-02-15", "trimestral")).toMatchObject({ inicio: "2026-01-01", fim: "2026-03-31" });
  });

  it("mensal acerta o último dia, inclusive em ano bissexto", () => {
    expect(periodoDe("2028-02-10", "mensal")).toEqual({
      inicio: "2028-02-01",
      fim: "2028-02-29",
      rotulo: "fev/2028",
    });
  });

  it("semestral", () => {
    expect(periodoDe("2026-07-01", "semestral")).toEqual({
      inicio: "2026-07-01",
      fim: "2026-12-31",
      rotulo: "2º semestre de 2026",
    });
  });

  it("vigência: período único", () => {
    expect(periodoDe("2026-11-10", "vigencia")).toEqual({
      inicio: "2000-01-01",
      fim: "2099-12-31",
      rotulo: "Vigência do TED",
    });
  });
});

describe("dataVizinha", () => {
  it("anda um período para trás e para a frente, virando o ano", () => {
    const q1 = periodoDe("2026-01-20", "trimestral");
    expect(dataVizinha(q1, -1)).toBe("2025-12-31");
    expect(periodoDe(dataVizinha(q1, -1), "trimestral").rotulo).toBe("4º trimestre de 2025");
    expect(dataVizinha(periodoDe("2026-12-05", "trimestral"), 1)).toBe("2027-01-01");
  });
});

describe("paraPeriodicidade", () => {
  it("aceita os quatro valores e cai no trimestral, como o backend", () => {
    expect(paraPeriodicidade("Mensal")).toBe("mensal");
    expect(paraPeriodicidade("vigencia")).toBe("vigencia");
    expect(paraPeriodicidade("anual")).toBe("trimestral");
    expect(paraPeriodicidade(null)).toBe("trimestral");
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
