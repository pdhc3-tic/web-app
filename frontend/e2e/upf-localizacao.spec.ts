import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

test.use({ storageState: storageStatePath("ugp") });

test("ficha exibe estado", async ({ page }) => {
  const upfId = primeiroUpfId();
  await page.goto(`/sgp/upfs/${upfId}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Localização" })).toBeVisible();

  const estadoValue = page.getByRole("definition").nth(0);
  await expect(estadoValue).not.toHaveText("—");
  await expect(estadoValue).toContainText(/[A-Z]{2}/);
});

test("municipio bloqueado sem estado", async ({ page }) => {
  await page.goto("/sgp/upfs/nova/");
  const municipioSelect = page.getByRole("combobox", { name: /município/i });
  await expect(municipioSelect).toBeDisabled();
});

test("municipios filtrados por estado", async ({ page }) => {
  await page.goto("/sgp/upfs/nova/");

  const estadoSelect = page.getByRole("combobox", { name: /estado/i });
  await expect(estadoSelect).toBeEnabled();
  await estadoSelect.click();
  await page.getByRole("option").filter({ hasText: /Rio Grande do Norte/i }).click();

  const municipioSelect = page.getByRole("combobox", { name: /município/i });
  await expect(municipioSelect).toBeEnabled();
  await municipioSelect.click();

  const opcoes = page.getByRole("option");
  await expect(opcoes.first()).toBeVisible();
  await expect(opcoes.filter({ hasText: /Mossoró|Natal/i }).first()).toBeVisible();
  await expect(opcoes.filter({ hasText: "Fortaleza" })).toHaveCount(0);

  await page.keyboard.press("Escape");
});

test("territorio automatico e readonly", async ({ page }) => {
  await page.goto("/sgp/upfs/nova/");

  const estadoSelect = page.getByRole("combobox", { name: /estado/i });
  await estadoSelect.click();
  await page.getByRole("option").filter({ hasText: /Rio Grande do Norte/i }).click();

  const municipioSelect = page.getByRole("combobox", { name: /município/i });
  await expect(municipioSelect).toBeEnabled();
  await municipioSelect.click();
  await page.getByRole("option").first().click();

  const territorioBox = page.locator("#upf-territorio");
  await expect(territorioBox).toBeVisible();
  await expect(territorioBox).not.toHaveText("—");
  await expect(territorioBox).not.toHaveAttribute("role", "combobox");
});

test("trocar estado limpa dependentes", async ({ page }) => {
  await page.goto("/sgp/upfs/nova/");

  const estadoSelect = page.getByRole("combobox", { name: /estado/i });
  const municipioSelect = page.getByRole("combobox", { name: /município/i });

  await estadoSelect.click();
  await page.getByRole("option").filter({ hasText: /Rio Grande do Norte/i }).click();
  await expect(municipioSelect).toBeEnabled();
  await municipioSelect.click();
  await page.getByRole("option").first().click();

  await estadoSelect.click();
  await page.getByRole("option").filter({ hasText: /Ceará/i }).click();

  await expect(municipioSelect).toHaveText(/Selecione o município/i);
  await expect(page.getByRole("combobox", { name: /comunidade/i })).toBeDisabled();
});

test("edicao abre preenchida", async ({ page }) => {
  const upfId = primeiroUpfId();
  await page.goto(`/sgp/upfs/${upfId}/editar/`);

  await expect(page.getByRole("list").filter({ has: page.getByText("Localização") })).toBeVisible();

  await expect(page.getByRole("combobox", { name: /estado/i })).not.toHaveText(/Selecione o estado/i);
  await expect(page.getByRole("combobox", { name: /município/i })).not.toHaveText(/Selecione o município/i);
  await expect(page.locator("#upf-territorio")).not.toHaveText("—");
});
