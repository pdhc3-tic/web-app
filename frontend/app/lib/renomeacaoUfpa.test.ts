import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

/**
 * #407 (AJ-FE-11) — a UPF passou a se chamar UFPA. O nome antigo só pode
 * sobrar no redirecionamento das rotas antigas e nos testes dele.
 */

const RAIZ = path.resolve(__dirname, "..", "..");
const NOME_ANTIGO = /upf/i;
/** Onde o nome antigo aparece de propósito, ou onde a sequência de letras é outra coisa. */
const PERMITIDOS = new Set([
  "next.config.ts",
  "app/lib/renomeacaoUfpa.test.ts",
  "e2e/ufpas-listagem.spec.ts",
  "package-lock.json",
]);
const FALSOS_POSITIVOS = /ArrowUpFromLine|setupFiles/g;

function arquivosVersionados(): string[] {
  return execFileSync("git", ["ls-files", "-z"], { cwd: RAIZ, encoding: "utf8" })
    .split("\0")
    .filter(Boolean);
}

describe("renomeação de UPF para UFPA (#407)", () => {
  const arquivos = arquivosVersionados();

  it("nenhum arquivo ou pasta guarda o nome antigo", () => {
    expect(arquivos.filter((a) => NOME_ANTIGO.test(a))).toEqual([]);
  });

  it("nenhum código, teste ou documento cita o nome antigo", { timeout: 60_000 }, () => {
    const comNomeAntigo = arquivos
      .filter((a) => !PERMITIDOS.has(a) && /\.(ts|tsx|mts|mjs|js|css|md|json)$/.test(a))
      .filter((a) => NOME_ANTIGO.test(readFileSync(path.join(RAIZ, a), "utf8").replace(FALSOS_POSITIVOS, "")));
    expect(comNomeAntigo).toEqual([]);
  });

  it("as rotas antigas redirecionam para as novas, com o resto do caminho", async () => {
    const redirects = await nextConfig.redirects!();
    expect(redirects).toContainEqual({ source: "/sgp/upfs", destination: "/sgp/ufpas", permanent: true });
    expect(redirects).toContainEqual({
      source: "/sgp/upfs/:path*",
      destination: "/sgp/ufpas/:path*",
      permanent: true,
    });
  });
});
