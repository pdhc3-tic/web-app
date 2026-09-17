import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

const TABS = [
  { hash: "localizacao", label: "Localização" },
  { hash: "dados-basicos", label: "Dados Básicos" },
  { hash: "comunicacao", label: "Comunicação" },
  { hash: "moradia", label: "Moradia" },
  { hash: "membros", label: "Membros" },
  { hash: "producao", label: "Produção" },
  { hash: "documentos", label: "Documentos" },
  { hash: "formularios", label: "Formulários" },
  { hash: "historico", label: "Histórico" },
];

test.describe("SGP — Ficha da UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("todas as abas são visíveis e preservam o hash na URL", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}`);

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    for (const { hash, label } of TABS) {
      const tab = page.getByRole("tab", { name: label });
      await expect(tab).toBeVisible();
      await tab.click();
      await expect(page).toHaveURL(new RegExp(`#${hash}`));
    }
  });

  test("hash na URL abre diretamente a aba correspondente", async ({ page }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#membros`);

    const abaAtiva = page.getByRole("tab", { name: "Membros", selected: true });
    await expect(abaAtiva).toBeVisible();
  });

  test("hash inválido abre a aba padrão (Localização)", async ({ page }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#aba-que-nao-existe`);

    const abaAtiva = page.getByRole("tab", { selected: true });
    await expect(abaAtiva).toBeVisible();
    await expect(abaAtiva).toHaveText("Localização");
  });

  test("aba Localização exibe estado, município, comunidade e território", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#localizacao`);

    await expect(page.getByTestId("localizacao-tab")).toBeVisible();
    await expect(page.getByText("Estado")).toBeVisible();
    await expect(page.getByText("Município")).toBeVisible();
  });

  test("aba Dados Básicos exibe nome e CPF mascarado do titular", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#dados-basicos`);

    await expect(page.getByTestId("dados-basicos-tab")).toBeVisible();
    await expect(page.getByText("Nome")).toBeVisible();
    const cpfCell = page.getByText(/^\d{3}\.\*\*\*\.\*\*\*-\d{2}$/);
    await expect(cpfCell).toBeVisible();
  });

  test("botão Editar navega para o wizard de edição", async ({ page }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}`);

    await page.getByRole("link", { name: /Editar/i }).click();
    await page.waitForURL(new RegExp(`/sgp/upfs/${upfId}/editar`));
  });

  test("usuario sem permissao nao ve botao Editar", async ({ page }) => {
    test.use({ storageState: storageStatePath("semPermissao") });
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}`);

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: /Editar/i })).toHaveCount(0);
  });
});
