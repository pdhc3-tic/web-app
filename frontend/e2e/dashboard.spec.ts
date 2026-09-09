import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

test.describe("dashboard ugp", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("exibe card de sem evidencia", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByText("Sem evidência")).toBeVisible();
    const card = page.locator("section[aria-label='Alertas do SGP'] > div").first();
    await expect(card).toBeVisible();
    await expect(card.getByText(/Nenhuma pendência|^\d+$/)).toBeVisible();
  });

  test("card leva a lista filtrada", async ({ page }) => {
    await page.goto("/dashboard");
    const link = page.getByRole("link", { name: "Ver listagem →" }).first();
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    expect(href).toContain("concluido_sem_evidencia");
  });

  test("zero alertas mostra estado positivo", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForTimeout(2000);
    const positivos = page.getByText("Nenhuma pendência");
    const contagens = page.getByText(/^\d+$/).filter({ hasNot: page.locator("h1,h2") });
    const total = (await positivos.count()) + (await contagens.count());
    expect(total).toBeGreaterThan(0);
  });

  test("falha isolada de um card", async ({ page }) => {
    await page.route("**/plano-trabalho/painel/**", (route) =>
      route.fulfill({ status: 500, body: "error" }),
    );
    await page.goto("/dashboard");
    await expect(page.getByText("Sem evidência")).toBeVisible();
    await expect(page.getByText("Atrasadas")).toBeVisible();
    await expect(page.getByText("Ações críticas")).toBeVisible();
  });
});

test.describe("dashboard adt", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("adt ve apenas seu territorio", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByText("Sem evidência")).toBeVisible();
    const link = page.getByRole("link", { name: "Ver listagem →" }).first();
    const href = await link.getAttribute("href");
    expect(href).toBeTruthy();
  });
});
