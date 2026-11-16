import { describe, expect, it } from "vitest";
import {
  formatarQuantidadeDeDiarias,
  hojeIso,
  montarGrade,
  situacaoDoValor,
  validarNovoValor,
  valorEditavel,
  type FaixaDestino,
  type ValorDiaria,
} from "./diarias";

/** #366 — regras de tela da tabela de diárias. */

const faixa = (id: number, nome: string, ordem: number): FaixaDestino => ({
  id,
  nome,
  ordem,
  padrao: null,
  ativo: true,
  enquadramentos: [],
});

const valor = (
  id: number,
  faixaId: number,
  inicio: string,
  fim: string | null,
  quanto: string,
  origem: ValorDiaria["origem"] = "federal",
): ValorDiaria => ({
  id,
  faixa_destino: faixaId,
  faixa_destino_nome: `Faixa ${faixaId}`,
  categoria_beneficiario: "padrao",
  vigencia_inicio: inicio,
  vigencia_fim: fim,
  valor: quanto,
  origem,
  criado_por_nome: null,
  criado_em: "2026-01-01T00:00:00Z",
});

const FAIXAS = [faixa(2, "Demais localidades", 2), faixa(1, "Capitais", 1)];
const VALORES = [
  valor(10, 1, "2026-01-01", "2026-06-30", "400.00"),
  valor(11, 1, "2026-07-01", null, "450.00", "fgd"),
  valor(20, 2, "2026-01-01", null, "300.00"),
];

describe("formatarQuantidadeDeDiarias", () => {
  it("mostra a meia diária com vírgula e concorda o plural", () => {
    expect(formatarQuantidadeDeDiarias("2.5")).toBe("2,5 diárias");
    expect(formatarQuantidadeDeDiarias("0.5")).toBe("0,5 diária");
    expect(formatarQuantidadeDeDiarias("1.0")).toBe("1 diária");
    expect(formatarQuantidadeDeDiarias(3)).toBe("3 diárias");
  });
});

describe("montarGrade", () => {
  const grade = montarGrade(FAIXAS, VALORES);

  it("as colunas são os inícios de vigência, do mais recente para o mais antigo", () => {
    expect(grade.vigencias).toEqual(["2026-07-01", "2026-01-01"]);
  });

  it("as linhas seguem a ordem das faixas", () => {
    expect(grade.linhas.map((l) => l.faixa.nome)).toEqual(["Capitais", "Demais localidades"]);
  });

  it("a célula traz o valor que a faixa tinha naquela data, com a origem", () => {
    const [capitais, demais] = grade.linhas;
    expect(capitais.celulas.map((c) => [c?.valor.valor, c?.valor.origem, c?.iniciaAqui])).toEqual([
      ["450.00", "fgd", true],
      ["400.00", "federal", true],
    ]);
    // A faixa que não mudou em julho segue com o valor de janeiro, marcado como anterior.
    expect(demais.celulas.map((c) => [c?.valor.valor, c?.iniciaAqui])).toEqual([
      ["300.00", false],
      ["300.00", true],
    ]);
  });

  it("faixa sem valor numa vigência fica com a célula vazia", () => {
    const nova = montarGrade([...FAIXAS, faixa(3, "Exterior", 3)], [...VALORES, valor(30, 3, "2026-07-01", null, "900.00")]);
    expect(nova.linhas[2].celulas.map((c) => c?.valor.valor ?? null)).toEqual(["900.00", null]);
  });

  it("o histórico da faixa vem do mais recente para o mais antigo", () => {
    expect(grade.linhas[0].historico.map((v) => v.id)).toEqual([11, 10]);
  });
});

describe("situação e valor editável", () => {
  const historico = [valor(12, 1, "2027-01-01", null, "500.00"), valor(11, 1, "2026-07-01", "2026-12-31", "450.00")];

  it("classifica pelo dia de hoje, com início e fim inclusivos", () => {
    expect(situacaoDoValor(historico[1], "2026-07-01")).toBe("vigente");
    expect(situacaoDoValor(historico[1], "2026-12-31")).toBe("vigente");
    expect(situacaoDoValor(historico[1], "2027-01-01")).toBe("encerrado");
    expect(situacaoDoValor(historico[0], "2026-12-31")).toBe("futuro");
  });

  it("edita o valor vigente hoje; sem ele, o que ainda está em aberto", () => {
    expect(valorEditavel(historico, "2026-11-13")?.id).toBe(11);
    expect(valorEditavel([historico[0]], "2026-11-13")?.id).toBe(12);
    expect(valorEditavel([], "2026-11-13")).toBeNull();
  });

  it("hojeIso usa o dia local", () => {
    expect(hojeIso(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});

describe("validarNovoValor", () => {
  const atual = { vigencia_inicio: "2026-07-01" };

  it("exige valor positivo e a data de início", () => {
    expect(validarNovoValor({ valor: null, vigencia_inicio: "" }, atual)).toEqual({
      valor: "Informe um valor maior que zero.",
      vigencia_inicio: "Informe a data de início da vigência.",
    });
    expect(validarNovoValor({ valor: "0.00", vigencia_inicio: "2026-08-01" }, atual).valor).toBeDefined();
  });

  it("a nova vigência começa depois do início da atual", () => {
    expect(validarNovoValor({ valor: "480.00", vigencia_inicio: "2026-07-01" }, atual).vigencia_inicio).toBe(
      "A nova vigência precisa começar depois do início da vigência atual.",
    );
    expect(validarNovoValor({ valor: "480.00", vigencia_inicio: "2026-07-02" }, atual)).toEqual({});
  });

  it("no primeiro valor da faixa, qualquer data serve", () => {
    expect(validarNovoValor({ valor: "480.00", vigencia_inicio: "2020-01-01" }, null)).toEqual({});
  });
});
