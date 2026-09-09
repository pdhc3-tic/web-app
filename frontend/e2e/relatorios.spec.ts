import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

test.describe("SGP — Relatórios (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("card Relatórios aparece na página do SGP com link funcional", async ({
    page,
  }) => {
    await page.goto("/sgp");
    const card = page.getByRole("link", { name: /Relatórios/i });
    await expect(card).toBeVisible();
    const href = await card.getAttribute("href");
    expect(href).toContain("/sgp/relatorios");
  });

  test("página de relatórios exibe os dois blocos de exportação", async ({
    page,
  }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByRole("heading", { name: "Plano de Trabalho" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Atividades de Campo" })).toBeVisible();
  });

  test("data de fim anterior ao início bloqueia exportação do PT", async ({
    page,
  }) => {
    await page.goto("/sgp/relatorios");

    const inputs = page.getByLabel("Período — início");
    await inputs.first().fill("2026-06-10");
    const inputsFim = page.getByLabel("Período — fim");
    await inputsFim.first().fill("2026-06-01");

    await page.getByRole("button", { name: "Exportar" }).first().click();
    await expect(
      page.getByText("O início do período não pode ser posterior ao fim."),
    ).toBeVisible();
  });

  test("exportação bem-sucedida do PT exibe toast de confirmação", async ({
    page,
  }) => {
    await page.route("**/api/v1/sgp/plano-trabalho/exportar/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/csv",
        headers: { "Content-Disposition": 'attachment; filename="plano_2026.csv"' },
        body: "col1,col2\nval1,val2",
      });
    });

    await page.goto("/sgp/relatorios");
    await page.getByRole("button", { name: "Exportar" }).first().click();
    await expect(page.getByText(/plano_2026\.csv/)).toBeVisible({ timeout: 10_000 });
  });

  test("exportação de atividades exibe toast com nome do arquivo", async ({
    page,
  }) => {
    await page.route("**/api/v1/sgp/atividades/exportar/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/csv",
        headers: { "Content-Disposition": 'attachment; filename="atividades_2026.csv"' },
        body: "titulo,status\nVisita,concluido",
      });
    });

    await page.goto("/sgp/relatorios");
    await page.getByRole("button", { name: "Exportar" }).nth(1).click();
    await expect(page.getByText(/atividades_2026\.csv/)).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("SGP — Relatórios (Super Admin)", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("super admin ve o bloco de integração Power BI", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(
      page.getByRole("heading", { name: /Power BI/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Gerenciar integração/i }),
    ).toBeVisible();
  });
});

test.describe("SGP — Relatórios (sem permissão)", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("usuario sem permissao nao ve bloco Power BI", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByRole("heading", { name: /Power BI/i })).toHaveCount(0);
  });

  test("botao exportar PT esta desabilitado para usuario sem permissao", async ({
    page,
  }) => {
    await page.goto("/sgp/relatorios");
    const btn = page.getByRole("button", { name: "Exportar" }).first();
    await expect(btn).toBeDisabled();
    await expect(page.getByText("Disponível para UGP e Super Admin.")).toBeVisible();
  });
});
