import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Listagem de UPFs — a tela que não tinha cobertura nenhuma.
 *
 * ─── Por que este arquivo existe ────────────────────────────────────────────
 *
 * O `UPFListSerializer` trocou `municipio` de string para objeto aninhado em
 * 5b63bde (21/07). O tipo do frontend seguiu dizendo `string`, a tabela
 * renderizou o objeto direto e a página inteira quebrava com "Objects are not
 * valid as a React child". Ficou assim por semanas porque nenhuma spec abria
 * /sgp/upfs — havia testes para o detalhe, o mapa e o cadastro, mas não para a
 * listagem.
 *
 * O teste 1 é deliberadamente básico: a regressão que importa aqui não é um
 * filtro sutil, é a tela não abrir.
 */

/** Abre a listagem e espera as linhas substituírem o skeleton. */
async function abrirListagem(page: Page): Promise<void> {
  await page.goto("/sgp/upfs");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

test.describe("Listagem de UPFs", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a tabela renderiza sem erro de React", async ({ page }) => {
    const erros: string[] = [];
    page.on("pageerror", (e) => erros.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") erros.push(msg.text());
    });

    await abrirListagem(page);

    // Uma linha de dados de verdade: se o município voltar como objeto outra
    // vez, o React derruba a árvore e nada disto aparece.
    const linha = page
      .getByRole("row")
      .filter({ hasText: /\d{2}\/\d{2}\/\d{4}/ })
      .first();
    await expect(linha).toBeVisible();

    expect(
      erros.filter((e) => /not valid as a React child/i.test(e)),
      `Erro de render na listagem:\n${erros.join("\n")}`,
    ).toHaveLength(0);
  });

  test("o município aparece como nome, não como objeto", async ({ page }) => {
    await abrirListagem(page);

    const linha = page
      .getByRole("row")
      .filter({ hasText: /\d{2}\/\d{2}\/\d{4}/ })
      .first();

    // "[object Object]" é o que sai quando um objeto é interpolado em texto —
    // o sintoma silencioso da mesma classe de bug.
    await expect(linha).not.toContainText("[object Object]");
    await expect(linha).not.toContainText("undefined");
  });

  test("clique na linha abre a ficha da UPF", async ({ page }) => {
    await abrirListagem(page);

    const linha = page
      .getByRole("row")
      .filter({ hasText: /\d{2}\/\d{2}\/\d{4}/ })
      .first();
    await linha.click();

    await expect(page).toHaveURL(/\/sgp\/upfs\/\d+\/?$/);
  });
});
