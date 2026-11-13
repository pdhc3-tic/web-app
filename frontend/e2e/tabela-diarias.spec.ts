import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #366 (SGD-REF-FE-08) — Tabela de diárias contra o backend real
 * (`/api/v1/sgd/config/diarias/`), com as faixas e os valores da carga inicial
 * (migration `0023_seed_faixas_diarias`).
 *
 * Só leitura: gravar valor, município ou parâmetro mudaria o cálculo das
 * diárias das outras specs. A edição está no teste de componente da página.
 */

const TELA = "/admin/configuracoes/sgd/diarias";

test.describe("Tabela de diárias — FGD", () => {
  test.use({ storageState: storageStatePath("fgd") });

  test("a FGD chega à tela pelo SGD e vê a grade, os municípios e os parâmetros", async ({ page }) => {
    await page.goto("/sgd");
    await page.getByRole("link", { name: /Tabela de diárias/ }).click();
    await expect(page).toHaveURL(/\/admin\/configuracoes\/sgd\/diarias\/?$/);

    const grade = page.getByTestId("grade-diarias");
    await expect(grade).toBeVisible();
    await expect(grade.getByRole("columnheader", { name: /A partir de \d{2}\/\d{2}\/\d{4}/ }).first()).toBeVisible();
    // Toda faixa da carga inicial tem valor, e cada valor diz de onde veio.
    await expect(grade.locator("tbody tr").first()).toContainText(/R\$\s?\d/);
    await expect(grade.getByText(/^(Federal|Valor FGD)$/).first()).toBeVisible();

    await expect(page.locator('[data-testid^="faixa-municipios-"]').first()).toBeVisible();
    await expect(page.getByTestId("parametros-diarias")).toBeVisible();
    await expect(page.getByTestId("parametros-diarias-salvar")).toBeDisabled();
  });

  test("editar um valor pede a data de início da nova vigência", async ({ page }) => {
    await page.goto(TELA);
    await page.locator('[data-testid^="grade-editar-"]').first().click();

    const form = page.getByTestId("valor-diaria-form");
    await expect(form.getByTestId("valor-diaria-atual")).toContainText("Valor atual");
    await form.getByLabel(/Novo valor da diária/).fill("50000");
    await page.getByTestId("valor-diaria-salvar").click();

    await expect(form.getByText("Informe a data de início da vigência.")).toBeVisible();
    await page.getByRole("button", { name: "Cancelar" }).click();
    await expect(form).toHaveCount(0);
  });

  test("o histórico da faixa mostra as vigências com a situação de cada uma", async ({ page }) => {
    await page.goto(TELA);
    await page.locator('[data-testid^="grade-historico-"]').first().click();

    const historico = page.locator('[data-testid^="historico-faixa-"]').first();
    await expect(historico).toContainText("Histórico de vigências");
    await expect(historico.locator("tbody tr").first()).toContainText(/Vigente|Encerrado|Ainda não vigora/);
  });
});

test.describe("Tabela de diárias — quem não configura", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o ADT não vê o atalho nem a tela", async ({ page }) => {
    await page.goto("/sgd");
    await expect(page.getByRole("link", { name: /Tabela de diárias/ })).toHaveCount(0);

    await page.goto(TELA);
    await expect(page.getByTestId("grade-diarias")).toHaveCount(0);
    await expect(page.getByTestId("parametros-diarias")).toHaveCount(0);
  });
});
