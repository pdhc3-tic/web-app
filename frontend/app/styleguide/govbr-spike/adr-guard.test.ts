import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Guard da ADR 001 (Issue #397): se alguém apagar as seções-chave sem abrir
 * uma nova ADR, o teste quebra e obriga a revisão. A ADR é o entregável
 * principal desta issue (label type:docs).
 */

const ADR_PATH = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "docs",
  "adr-001-govbr-ds-tailwind.md",
);
const ADR = readFileSync(ADR_PATH, "utf8");

describe("ADR 001 — GOV.BR DS e Tailwind", () => {
  it("define status, data e issue", () => {
    expect(ADR).toMatch(/\*\*Status:\*\*/);
    expect(ADR).toMatch(/\*\*Data:\*\*/);
    expect(ADR).toMatch(/\*\*Issue:\*\* #397/);
  });

  it("cobre as quatro frentes pedidas pelos critérios de aceitação", () => {
    expect(ADR).toMatch(/prefix\(tw\)/);
    expect(ADR).toMatch(/preflight/i);
    expect(ADR).toMatch(/divisão de responsabilidade/i);
    expect(ADR).toMatch(/codemod/i);
    expect(ADR).toMatch(/ordem de migração/i);
  });

  it("entrega a tabela de migração por lote com estimativa", () => {
    expect(ADR).toMatch(/\| Lote \|/);
    expect(ADR).toMatch(/\| 1 \(piloto\) \|/);
    expect(ADR).toMatch(/Total estimado:/);
  });

  it("referencia o spike na rota do styleguide", () => {
    expect(ADR).toMatch(/\/styleguide\/govbr-spike/);
  });
});
