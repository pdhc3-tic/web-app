import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { CHAVES_CHOICES, ChoicesInvalidosError, fetchSgpChoices, rotuloDe } from "./choices";

/**
 * #272 — Fonte única para os choices do SGP: `GET /api/v1/choices/`.
 */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

function respostaCompleta(): Record<string, { value: string | number; label: string }[]> {
  return Object.fromEntries(
    CHAVES_CHOICES.map((chave) => [chave, [{ value: 1, label: `${chave} um` }]]),
  );
}

function responder(corpo: unknown) {
  api.client.mockResolvedValue({ json: async () => corpo });
}

describe("fetchSgpChoices", () => {
  it("devolve todas as listas, com o value como texto (o <Select> opera com string)", async () => {
    responder(respostaCompleta());
    const choices = await fetchSgpChoices();
    expect(Object.keys(choices).sort()).toEqual([...CHAVES_CHOICES].sort());
    expect(choices.genero).toEqual([{ value: "1", label: "genero um" }]);
  });

  it("falha com erro explícito quando falta uma lista — nada de cópia local", async () => {
    const corpo = respostaCompleta();
    delete corpo.seguridade_social;
    responder(corpo);
    await expect(fetchSgpChoices()).rejects.toThrow(ChoicesInvalidosError);
    await expect(fetchSgpChoices()).rejects.toThrow(/seguridade_social/);
  });

  it("falha quando um item vem sem rótulo", async () => {
    responder({ ...respostaCompleta(), saude: [{ value: "diabetes" }] });
    await expect(fetchSgpChoices()).rejects.toThrow(/saude/);
  });

  it("propaga o erro da API (rede, 5xx) para a tela explicar", async () => {
    api.client.mockImplementation(() => Promise.reject(new Error("Erro inesperado (500)")));
    const erro = await fetchSgpChoices().catch((e: unknown) => e);
    expect((erro as Error).message).toBe("Erro inesperado (500)");
  });
});

describe("rotuloDe", () => {
  const opcoes = [{ value: "1", label: "Feminino" }];
  it("acha o rótulo pelo valor, mesmo numérico", () => {
    expect(rotuloDe(opcoes, 1)).toBe("Feminino");
  });
  it("devolve o próprio valor quando não acha, e vazio para nulo", () => {
    expect(rotuloDe(opcoes, "9")).toBe("9");
    expect(rotuloDe(opcoes, null)).toBe("");
  });
});

/**
 * Guarda da issue ("sem hardcode remanescente"): nenhuma lista que o endpoint
 * publica volta a ser escrita à mão no frontend.
 */
describe("sem lista de choices duplicada no frontend", () => {
  const RAIZ = path.resolve(__dirname, "..");
  const arquivos: string[] = [];
  (function varrer(dir: string) {
    for (const nome of readdirSync(dir)) {
      const p = path.join(dir, nome);
      if (statSync(p).isDirectory()) {
        if (nome !== "node_modules" && nome !== "styleguide") varrer(p);
      } else if (/\.(ts|tsx)$/.test(nome) && !/\.test\.tsx?$/.test(nome)) {
        arquivos.push(p);
      }
    }
  })(RAIZ);

  // Nomes das listas que existiam espelhadas e foram removidas.
  const REMOVIDAS = [
    "FALLBACK_CHOICES",
    "GENERO_OPTIONS",
    "COR_RACA_OPTIONS",
    "ESCOLARIDADE_OPTIONS",
    "DISPOSITIVO_OPTIONS",
    "PCT_OPTIONS",
    "POSSE_TERRA_OPTIONS",
    "SITUACAO_MORADIA_OPTIONS",
    "TIPO_MORADIA_OPTIONS",
    "MATERIAL_CONSTRUCAO_OPTIONS",
    "ENERGIA_OPTIONS",
    "AGUA_OPTIONS",
    "SEGURIDADE_OPTIONS",
    "PARENTESCO_OPTIONS",
    "SAUDE_OPTIONS",
    "ODS_OPTIONS",
    "TIPO_ATIVIDADE_OPTIONS",
    "FORMA_ATUACAO_OPTIONS",
    "AMBITO_OPTIONS",
    "TIPO_DOC_OPTIONS",
    "TIPO_DOC_ATIVIDADE_OPTIONS",
    "SISTEMA_CRIACAO_OPTIONS",
    "TIPO_OUTRA_OPTIONS",
  ];

  it.each(REMOVIDAS)("%s não volta a existir", (nome) => {
    const onde = arquivos.filter((p) => new RegExp(`\\b${nome}\\b`).test(readFileSync(p, "utf8")));
    expect(onde.map((p) => path.relative(RAIZ, p))).toEqual([]);
  });

  it("nenhum valor de choice do backend aparece numa lista literal de opções", () => {
    // Amostra de valores que só existem nas listas do backend.
    const VALORES = [
      "visita_tecnica",
      "realizacao",
      "microrregional",
      "deficiencia_visual",
      "bolsa_familia",
      "semi_intensivo",
      "extrativismo",
      "lista_presenca",
      "dap_caf",
    ];
    const literal = new RegExp(`\\{\\s*value:\\s*"(${VALORES.join("|")})"\\s*,\\s*label:`);
    const onde = arquivos.filter((p) => literal.test(readFileSync(p, "utf8")));
    expect(onde.map((p) => path.relative(RAIZ, p))).toEqual([]);
  });
});
