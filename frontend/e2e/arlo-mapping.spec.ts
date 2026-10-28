import { expect, test, type Page } from "@playwright/test";
import {
  criarArloMappingFixture,
  removerArloMappingFixture,
  type ArloMappingFixture,
} from "./helpers/arloMappingFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Configuração do mapeamento Arlo ↔ SGD (#320, SGD-FE-9) em
 * /admin/configuracoes/sgd/integracao-arlo, contra o backend real da BE-9: o
 * CRUD, o catálogo (`campos/`) e o preview da exportação (`preview/`).
 *
 * Parte do mapeamento padrão da migration `sgd.0007` (10 colunas na
 * exportação, 6 na importação); a fixture devolve o mapeamento à foto do
 * setup no fim.
 */

let fx: ArloMappingFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarArloMappingFixture();
});

test.afterAll(() => {
  if (fx) removerArloMappingFixture(fx);
});

const PAGE_URL = "/admin/configuracoes/sgd/integracao-arlo";
const API = "/api/v1/sgd/config/arlo-mapping/";

async function abrir(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("arlo-mapping-page")).toBeVisible();
  await expect(page.getByTestId("arlo-linha-demanda_id")).toBeVisible();
}

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao, exact: true }).click();
}

async function camposNaOrdem(page: Page): Promise<string[]> {
  return page
    .locator('tr[data-testid^="arlo-linha-"]')
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")!.replace("arlo-linha-", "")));
}

/** Cabeçalho do preview, na ordem em que o backend monta o CSV. */
function cabecalhoDoPreview(page: Page) {
  return page.getByTestId("arlo-preview").locator("thead th");
}

test.describe("Mapeamento Arlo ↔ SGD — Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("rótulos e obrigatoriedade vêm do catálogo do backend; o preview mostra a linha do CSV", async ({
    page,
  }) => {
    await abrir(page);
    const linha = page.getByTestId("arlo-linha-demanda_id");
    await expect(linha.getByText("ID da demanda")).toBeVisible();
    await expect(linha.getByText("Obrigatório")).toBeVisible();
    await expect(page.getByTestId("arlo-linha-solicitacao_id").getByText("Obrigatório")).toHaveCount(0);

    const exportacao = fx.colunas.filter((c) => c.direcao === "exportacao" && c.ativo);
    await expect(cabecalhoDoPreview(page)).toHaveText(exportacao.map((c) => c.coluna_arlo));
  });

  test("cria uma coluna e o preview passa a trazê-la", async ({ page }) => {
    await abrir(page);
    await page.getByTestId("arlo-novo").click();
    await escolher(page, "arlo-campo", "Valor estimado");
    await page.locator("#arlo-coluna").fill("Valor Estimado E2E");
    await escolher(page, "arlo-formato", "Moeda");
    const criacao = page.waitForResponse((r) => r.url().endsWith(API) && r.request().method() === "POST");
    await page.getByTestId("arlo-salvar").click();
    expect((await criacao).status()).toBe(201);

    await expect(page.getByText("Coluna adicionada.")).toBeVisible();
    const nova = page.getByTestId("arlo-linha-valor_estimado");
    await expect(nova).toContainText("Valor Estimado E2E");
    await expect(nova).toContainText("Moeda");
    await expect(cabecalhoDoPreview(page).last()).toHaveText("Valor Estimado E2E");
  });

  test("remove a coluna criada e fecha o painel e a confirmação", async ({ page }) => {
    await abrir(page);
    await page.getByRole("button", { name: "Editar Valor estimado" }).click();
    await page.getByTestId("arlo-remover").click();
    await expect(page.getByRole("dialog", { name: "Remover esta coluna?" })).toBeVisible();

    const remocao = page.waitForResponse((r) => r.url().includes(API) && r.request().method() === "DELETE");
    await page.getByTestId("arlo-confirmar-remocao").click();
    expect((await remocao).status()).toBe(204);

    await expect(page.getByText("Coluna removida.")).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByTestId("arlo-linha-valor_estimado")).toHaveCount(0);
    await expect(cabecalhoDoPreview(page)).not.toContainText(["Valor Estimado E2E"]);
  });

  test("edita o nome da coluna e o preview reflete a edição", async ({ page }) => {
    await abrir(page);
    await page.getByRole("button", { name: "Editar Título da demanda" }).click();
    await expect(page.locator("button#arlo-campo")).toBeDisabled();
    await page.locator("#arlo-coluna").fill("Título E2E");
    const edicao = page.waitForResponse((r) => r.url().includes(API) && r.request().method() === "PATCH");
    await page.getByTestId("arlo-salvar").click();
    expect((await edicao).status()).toBe(200);

    await expect(page.getByText("Mapeamento atualizado.")).toBeVisible();
    await expect(page.getByTestId("arlo-linha-titulo")).toContainText("Título E2E");
    await expect(cabecalhoDoPreview(page)).toContainText(["Título E2E"]);
    await expect(cabecalhoDoPreview(page).getByText("Título", { exact: true })).toHaveCount(0);
  });

  test("arrastar pela alça reordena, grava a ordem e muda o preview", async ({ page }) => {
    await abrir(page);
    const antes = await camposNaOrdem(page);
    const linhas = page.locator('tr[data-testid^="arlo-linha-"]');

    const reordenacao = page.waitForResponse((r) => r.url().endsWith(`${API}reordenar/`));
    await linhas.nth(1).locator("[data-arlo-handle]").dragTo(linhas.nth(0));
    expect((await reordenacao).status()).toBe(200);

    await expect(page.getByText("Ordem salva.")).toBeVisible();
    await expect.poll(() => camposNaOrdem(page)).toEqual([antes[1], antes[0], ...antes.slice(2)]);
    const segunda = fx.colunas.find((c) => c.direcao === "exportacao" && c.campo_sgd === antes[1])!;
    await expect(cabecalhoDoPreview(page).first()).toHaveText(segunda.coluna_arlo);

    // A ordem é do backend: recarregar a página mantém a nova sequência.
    await abrir(page);
    expect((await camposNaOrdem(page)).slice(0, 2)).toEqual([antes[1], antes[0]]);
  });

  test("os botões ↑/↓ também reordenam", async ({ page }) => {
    await abrir(page);
    const antes = await camposNaOrdem(page);
    const reordenacao = page.waitForResponse((r) => r.url().endsWith(`${API}reordenar/`));
    await page.getByTestId(`arlo-linha-${antes[1]}`).getByRole("button", { name: /para cima/ }).click();
    expect((await reordenacao).status()).toBe(200);
    await expect.poll(() => camposNaOrdem(page)).toEqual([antes[1], antes[0], ...antes.slice(2)]);
  });

  test("a aba de importação lista as colunas do retorno, sem reordenação nem preview", async ({ page }) => {
    await abrir(page);
    await page.getByTestId("arlo-tab-importacao").click();
    await expect(page.getByTestId("arlo-linha-data_pagamento")).toContainText("Data do pagamento");
    await expect(page.locator("[data-arlo-handle]")).toHaveCount(0);
    await expect(page.getByTestId("arlo-preview")).toHaveCount(0);
  });
});

test.describe("Mapeamento Arlo ↔ SGD — fora do Super Admin", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("quem não é Super Admin vê o acesso restrito", async ({ page }) => {
    await page.goto(PAGE_URL);
    await expect(page.getByText("Conteúdo restrito")).toBeVisible();
    await expect(page.getByTestId("arlo-mapping-page")).toHaveCount(0);
  });
});
