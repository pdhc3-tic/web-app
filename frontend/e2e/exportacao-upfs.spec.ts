import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

const EXPORTAR_API = "**/api/v1/sgp/upfs/exportar/**";

test.describe("SGP — Exportação da listagem de UPFs", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("botão Exportar está visível na listagem de UPFs", async ({ page }) => {
    await page.goto("/sgp/upfs");
    await expect(
      page.getByRole("button", { name: "Exportar" }),
    ).toBeVisible();
  });

  test("exportação bem-sucedida exibe toast com nome do arquivo", async ({
    page,
  }) => {
    await page.route(EXPORTAR_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/csv",
        headers: {
          "Content-Disposition": 'attachment; filename="upfs_2026-06-01.csv"',
        },
        body: "nome,cpf,municipio\nJoão Silva,529.***.***-25,Ouricuri",
      });
    });

    await page.goto("/sgp/upfs");
    await page.getByRole("button", { name: "Exportar" }).click();
    await expect(page.getByText(/upfs_2026-06-01\.csv/)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("exportação inclui os filtros ativos da listagem", async ({ page }) => {
    let exportUrl: string | null = null;

    await page.route(EXPORTAR_API, async (route) => {
      exportUrl = route.request().url();
      await route.fulfill({
        status: 200,
        contentType: "text/csv",
        body: "nome,cpf",
      });
    });

    await page.goto("/sgp/upfs?municipio=1001&status=inativas");
    await page.getByRole("button", { name: "Exportar" }).click();
    await page.waitForTimeout(1_500);

    expect(exportUrl).toBeTruthy();
    expect(exportUrl).toContain("municipio=1001");
    expect(exportUrl).toContain("status=inativas");
  });

  test("erro na exportação exibe toast de erro", async ({ page }) => {
    await page.route(EXPORTAR_API, async (route) => {
      await route.fulfill({ status: 500, body: "Internal Server Error" });
    });

    await page.goto("/sgp/upfs");
    await page.getByRole("button", { name: "Exportar" }).click();
    await expect(page.getByText(/Não foi possível exportar/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("exportação com mais de 1000 registros exibe aviso antes do download", async ({
    page,
  }) => {
    await page.route("**/api/v1/sgp/upfs/**", async (route) => {
      const url = route.request().url();
      if (url.includes("exportar")) {
        await route.fulfill({
          status: 200,
          contentType: "text/csv",
          body: "nome,cpf",
        });
      } else if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1500,
            next: null,
            previous: null,
            results: [],
          }),
        });
      } else {
        await route.fallback();
      }
    });

    await page.goto("/sgp/upfs");
    await page.getByRole("button", { name: "Exportar" }).click();

    await expect(page.getByText(/1.500 registros/i)).toBeVisible({
      timeout: 5_000,
    });
  });
});
