import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #272 — Fonte única para os choices: `GET /api/v1/choices/`.
 *
 * Os formulários mostram o que a API publica (o rótulo é trocado na resposta
 * para provar que vem dela, e não de uma cópia no frontend); uma falha na carga
 * aparece como erro explícito; e a lista é buscada uma vez por sessão.
 */

const ROTA_CHOICES = (url: URL) => url.pathname === "/api/v1/choices/";
const CORS = { "access-control-allow-origin": "*" };

/** Repassa a resposta real trocando o rótulo do 1º item de `chave`. */
async function marcarRotulo(page: Page, chave: string, rotulo: string) {
  await page.route(ROTA_CHOICES, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const resposta = await route.fetch();
    const corpo = await resposta.json();
    corpo[chave][0].label = rotulo;
    await route.fulfill({ response: resposta, json: corpo });
  });
}

test.describe("Choices do SGP (#272)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("o formulário de atividade usa as opções publicadas pela API", async ({ page }) => {
    await marcarRotulo(page, "tipo_atividade", "Visita técnica (via API)");
    await page.goto("/sgp/atividades/nova");

    await page.locator("button#atividade-tipo-atividade").click();
    await expect(page.getByRole("option", { name: "Visita técnica (via API)" })).toBeVisible();
  });

  test("o filtro de Produção usa as opções publicadas pela API", async ({ page }) => {
    await marcarRotulo(page, "producao_tipo", "Agrícola (via API)");
    await page.goto("/sgp/producao");

    await page.getByRole("combobox", { name: "Tipo" }).click();
    await expect(page.getByRole("option", { name: "Agrícola (via API)" })).toBeVisible();
  });

  test("falha ao carregar: aviso explícito, e tentar de novo recupera as listas", async ({ page }) => {
    let falhar = true;
    await page.route(ROTA_CHOICES, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      if (falhar) return route.fulfill({ status: 500, headers: CORS, body: "erro" });
      return route.fallback();
    });

    await page.goto("/sgp/atividades/nova");
    const aviso = page.getByTestId("choices-indisponiveis");
    await expect(aviso).toBeVisible({ timeout: 20_000 });
    await expect(aviso).toContainText("Não foi possível carregar as opções dos formulários");

    falhar = false;
    await aviso.getByRole("button", { name: "Tentar novamente" }).click();
    await expect(aviso).toHaveCount(0);

    await page.locator("button#atividade-tipo-atividade").click();
    await expect(page.getByRole("option").first()).toBeVisible();
  });

  test("as listas são buscadas uma vez: navegar entre telas não refaz a requisição", async ({
    page,
  }) => {
    let requisicoes = 0;
    page.on("request", (r) => {
      if (new URL(r.url()).pathname === "/api/v1/choices/" && r.method() === "GET") requisicoes++;
    });

    await page.goto("/sgp");
    await expect.poll(() => requisicoes, { timeout: 30_000 }).toBe(1);

    // Navegação pelo app (sem recarregar a página): o cache vale para todas.
    const menu = page.getByRole("navigation", { name: /./ }).first();
    await menu.getByRole("link", { name: "SGD", exact: true }).click();
    await expect(page).toHaveURL(/\/sgd\/?$/);
    await menu.getByRole("link", { name: "SGP", exact: true }).click();
    await expect(page).toHaveURL(/\/sgp\/?$/);
    await menu.getByRole("link", { name: "SCA", exact: true }).click();
    await expect(page).toHaveURL(/\/sca\/?$/);
    await page.waitForLoadState("networkidle");

    expect(requisicoes).toBe(1);
  });
});
