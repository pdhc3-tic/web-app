// @vitest-environment node
import { readFileSync } from "node:fs";
import path from "node:path";
import postcss from "postcss";
import tailwindcss from "@tailwindcss/postcss";
import { describe, expect, it } from "vitest";

/**
 * O CSS do spike (#397) é compilado por `npm run build:govbr-spike` e fica
 * versionado em public/. Este teste recompila e compara, para o arquivo
 * publicado não ficar para trás quando o documento do iframe mudar.
 */
const ENTRADA = path.resolve(__dirname, "govbr-spike.css");
const PUBLICADO = path.resolve(__dirname, "../../../public/govbr-spike.css");
const semCR = (s: string) => s.replace(/\r\n/g, "\n");

describe("CSS do spike GOV.BR DS (#397)", () => {
  it("o arquivo publicado está em dia com o documento do iframe", async () => {
    const { css } = await postcss([tailwindcss()]).process(readFileSync(ENTRADA, "utf8"), {
      from: ENTRADA,
      to: PUBLICADO,
    });
    expect(semCR(readFileSync(PUBLICADO, "utf8")), "rode npm run build:govbr-spike").toBe(semCR(css));
  }, 30_000);

  it("tem o prefixo tw: da v4 e as variantes, sem o reset do preflight", () => {
    const css = readFileSync(PUBLICADO, "utf8");
    expect(css).toContain(".tw\\:grid");
    expect(css).toContain(".tw\\:sm\\:grid-cols-2");
    expect(css).toContain("--tw-spacing");
    expect(css).not.toContain("box-sizing: border-box");
    expect(css).not.toContain("::file-selector-button");
  });
});
