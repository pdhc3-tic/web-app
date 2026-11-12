import { describe, expect, it } from "vitest";
import {
  configDoSchema,
  configDoTipo,
  montarCamposJson,
  problemasDoSchema,
  resumoSolicitacao,
  validarCampos,
  valoresDoCamposJson,
} from "@/app/lib/camposSolicitacao";
import type { SchemaCampos } from "@/app/lib/tiposSolicitacao";

/** #365 — o formulário de um tipo novo do catálogo, desenhado pelo `schema_campos`. */

const HOSPEDAGEM: SchemaCampos = {
  type: "object",
  required: ["hotel", "diarias", "check_in", "categoria"],
  properties: {
    observacoes: { type: "string", title: "Observações", maxLength: 500, "x-ordem": 6 },
    hotel: { type: "string", title: "Hotel", description: "Nome do estabelecimento", "x-ordem": 1 },
    diarias: { type: "integer", title: "Número de diárias", minimum: 1, mensagem: "Pelo menos uma diária.", "x-ordem": 2 },
    valor_diaria: { type: "number", title: "Valor da diária", "x-ordem": 3 },
    check_in: { type: "string", format: "date", title: "Check-in", "x-ordem": 4 },
    chegada: { type: "string", format: "date-time", title: "Chegada prevista", "x-ordem": 5 },
    categoria: {
      title: "Categoria",
      oneOf: [
        { const: "simples", title: "Simples" },
        { const: "luxo", title: "Luxo" },
      ],
      "x-ordem": 7,
    },
    cafe: { type: "boolean", title: "Café incluso?", "x-ordem": 8 },
    regiao: { enum: ["norte", "sul"], title: "Região", "x-ordem": 9 },
  },
};

describe("configDoSchema (#365)", () => {
  const { campos, valorDigitado } = configDoSchema(HOSPEDAGEM);
  const campo = (chave: string) => campos.find((c) => c.chave === chave)!;

  it("segue a ordem de x-ordem e digita o valor estimado", () => {
    expect(campos.map((c) => c.chave)).toEqual([
      "hotel", "diarias", "valor_diaria", "check_in", "chegada", "observacoes", "categoria", "cafe", "regiao",
    ]);
    expect(valorDigitado).toBe(true);
  });

  it("mapeia cada tipo de campo, com rótulo, ajuda e obrigatório", () => {
    expect(campo("hotel")).toMatchObject({ tipo: "texto", rotulo: "Hotel", ajuda: "Nome do estabelecimento", obrigatorio: true });
    expect(campo("diarias")).toMatchObject({ tipo: "numero", inteiro: true, minimo: 1, obrigatorio: true });
    expect(campo("valor_diaria")).toMatchObject({ tipo: "numero", inteiro: false, obrigatorio: false });
    expect(campo("check_in")).toMatchObject({ tipo: "data" });
    expect(campo("chegada")).toMatchObject({ tipo: "dataHora", isoCompleto: true });
    expect(campo("observacoes")).toMatchObject({ tipo: "textarea", largo: true });
    expect(campo("cafe")).toMatchObject({ tipo: "booleano" });
    expect(campo("categoria").opcoes).toEqual([
      { value: "simples", label: "Simples", original: "simples" },
      { value: "luxo", label: "Luxo", original: "luxo" },
    ]);
    expect(campo("regiao").opcoes).toEqual([
      { value: "norte", label: "norte", original: "norte" },
      { value: "sul", label: "sul", original: "sul" },
    ]);
  });

  it("sem x-ordem, os obrigatórios vêm primeiro, na ordem do required", () => {
    const { campos: semOrdem } = configDoSchema({
      required: ["b", "a"],
      properties: { z: { type: "string" }, a: { type: "string" }, b: { type: "string" } },
    });
    expect(semOrdem.map((c) => c.chave)).toEqual(["b", "a", "z"]);
    expect(semOrdem[2].rotulo).toBe("z");
  });

  it("os seis tipos de origem mantêm o layout próprio, ignorando o schema", () => {
    expect(configDoTipo("veiculo", HOSPEDAGEM).campos[0].chave).toBe("tipo_veiculo");
    expect(configDoTipo("hospedagem", HOSPEDAGEM).campos[0].chave).toBe("hotel");
  });
});

describe("problemasDoSchema — estrutura que o renderizador lê (revisão do PR #420)", () => {
  it.each([
    [[], "O schema precisa ser um objeto JSON."],
    [{ properties: [] }, "“properties” precisa ser um objeto"],
    [{ required: "hotel" }, "“required” precisa ser uma lista"],
    [{ properties: { hotel: null } }, "O campo “hotel” precisa ser um objeto"],
    [{ properties: { hotel: "texto" } }, "O campo “hotel” precisa ser um objeto"],
    [{ properties: { hotel: { title: { pt: "Hotel" } } } }, "O “title” do campo “hotel”"],
    [{ properties: { hotel: { type: 1 } } }, "O “type” do campo “hotel”"],
    [{ properties: { cat: { enum: "a" } } }, "O “enum” do campo “cat”"],
    [{ properties: { cat: { enum: [{ a: 1 }] } } }, "O “enum” do campo “cat”"],
    [{ properties: { q: { oneOf: [null] } } }, "O “oneOf” do campo “q”"],
    [{ properties: { n: { minimum: "1" } } }, "O “minimum” do campo “n”"],
  ])("%j → erro", (schema, trecho) => {
    expect(problemasDoSchema(schema)).toContain(trecho);
  });

  it("aceita o que o backend aceita, mesmo o que o formulário desenha como texto", () => {
    expect(problemasDoSchema(HOSPEDAGEM)).toBeNull();
    expect(problemasDoSchema({})).toBeNull();
    expect(
      problemasDoSchema({
        type: "object",
        properties: {
          hospede: { type: "object", required: ["nome"] },
          qtd: { type: ["integer", "string"], pattern: "^\\d+$", minimum: 1 },
          ok: { enum: [true, false, null] },
        },
        allOf: [{ if: { properties: { ok: { const: true } } }, then: { required: ["qtd"] } }],
      }),
    ).toBeNull();
  });

  it("um schema salvo malformado não derruba a montagem: o campo inválido fica de fora", () => {
    const config = configDoSchema({
      required: "hotel",
      properties: { hotel: null, nome: { title: { x: 1 }, description: 3 }, cidade: { type: "string" } },
    } as unknown as SchemaCampos);
    expect(config.campos.map((c) => [c.chave, c.rotulo, c.ajuda])).toEqual([
      ["cidade", "cidade", undefined],
      ["nome", "nome", undefined],
    ]);
    expect(configDoSchema({ properties: [] } as unknown as SchemaCampos).campos).toEqual([]);
  });
});

describe("validação e payload de um tipo do catálogo (#365)", () => {
  const config = configDoSchema(HOSPEDAGEM);

  it("obrigatórios, inteiro e mínimo com a mensagem do schema", () => {
    const erros = validarCampos("hospedagem", config, { diarias: "0", valor_diaria: "abc" });
    expect(erros.hotel).toBe("Campo obrigatório.");
    expect(erros.diarias).toBe("Pelo menos uma diária.");
    expect(erros.valor_diaria).toBe("Informe um número.");
    expect(validarCampos("hospedagem", config, { diarias: "1.5" }).diarias).toBe("Informe um número inteiro.");
  });

  it("monta o campos_json com os tipos do schema e volta ao formulário", () => {
    const valores = {
      hotel: " Pousada do Sertão ",
      diarias: "2",
      valor_diaria: "180,50",
      check_in: "2026-12-10",
      chegada: "2026-12-10T14:30",
      categoria: "simples",
      cafe: "sim",
      observacoes: "",
    };
    const json = montarCamposJson(config, valores);
    expect(json).toMatchObject({
      hotel: "Pousada do Sertão",
      diarias: 2,
      valor_diaria: 180.5,
      check_in: "2026-12-10",
      categoria: "simples",
      cafe: true,
    });
    expect(json).not.toHaveProperty("observacoes");
    // date-time do JSON Schema: ISO completo, que volta ao datetime-local no mesmo horário local.
    expect(String(json.chegada)).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    expect(valoresDoCamposJson(config, json)).toMatchObject({ chegada: "2026-12-10T14:30", cafe: "sim", diarias: "2" });
  });

  it("enumeração numérica vai como número, não como o texto do select", () => {
    const numerica = configDoSchema({
      properties: {
        estrelas: { enum: [3, 4, 5], title: "Estrelas" },
        quartos: { oneOf: [{ const: 1, title: "Individual" }, { const: 2, title: "Duplo" }], title: "Quarto" },
      },
    });
    expect(montarCamposJson(numerica, { estrelas: "4", quartos: "2" })).toEqual({ estrelas: 4, quartos: 2 });
    expect(valoresDoCamposJson(numerica, { estrelas: 4, quartos: 2 })).toEqual({ estrelas: "4", quartos: "2" });
  });

  it("o resumo do cartão usa os dois primeiros campos preenchidos, com o rótulo da opção", () => {
    expect(resumoSolicitacao("hospedagem", { hotel: "Pousada do Sertão", diarias: 2 }, HOSPEDAGEM)).toBe(
      "Pousada do Sertão · 2",
    );
    expect(
      resumoSolicitacao("x", { categoria: "luxo" }, { properties: { categoria: HOSPEDAGEM.properties!.categoria } }),
    ).toBe("Luxo");
  });
});
