import { describe, expect, it } from "vitest";
import { rotuloDoPeriodo } from "./rotuloDoPeriodo";

describe("rotuloDoPeriodo (#467)", () => {
  const dia = new Date(2026, 10, 26, 10, 0);

  it("mês: só a primeira letra em maiúscula", () => {
    expect(rotuloDoPeriodo("mes", dia)).toBe("Novembro de 2026");
  });

  it("dia: o mês fica em minúscula, como na escrita corrente", () => {
    expect(rotuloDoPeriodo("dia", dia)).toBe("26 de novembro de 2026");
  });

  it("semana: de domingo a sábado", () => {
    expect(rotuloDoPeriodo("semana", dia)).toBe("22/11 — 28/11 de 2026");
  });
});
