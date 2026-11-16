import { expect, test, type Page } from "@playwright/test";
import {
  criarMeuSaldoFixture,
  removerMeuSaldoFixture,
  type MeuSaldoFixture,
} from "./helpers/meuSaldoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #401 — "Meu saldo" com extrato (backend AJ-BE-06, PR #414), contra o backend
 * real. O ADT acompanha o limite de cada rubrica, submete uma demanda pela tela
 * e vê a reserva no extrato; com a rubrica em amarelo, o atalho do recurso
 * extra lista a demanda que ainda está em rascunho.
 */

let fx: MeuSaldoFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarMeuSaldoFixture();
});

test.afterAll(() => {
  removerMeuSaldoFixture();
});

const card = (page: Page) => page.getByTestId("meu-saldo-card-locacao-veiculo");

async function abrir(page: Page) {
  await page.goto("/sgp/orcamento/meu-saldo");
  await expect(card(page)).toBeVisible();
}

test.describe("ADT/ACR", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("chega pelo hub do SGP e vê o card da rubrica sem nada usado", async ({ page }) => {
    await page.goto("/sgp");
    await page.getByTestId("sgp-hub-card-meu-saldo").click();
    await expect(page).toHaveURL(/\/sgp\/orcamento\/meu-saldo\/?$/);

    await expect(card(page)).toHaveAttribute("data-semaforo", "verde");
    await expect(card(page).getByTestId("meu-saldo-disponivel")).toContainText("R$ 1.000,00");
    await expect(card(page).getByTestId("meu-saldo-comprometido")).toContainText("R$ 0,00");
    await expect(card(page).getByTestId("meu-saldo-recurso-extra")).toHaveCount(0);
  });

  test("submete a demanda e a reserva aparece no card e no extrato", async ({ page }) => {
    await page.goto(`/sgd/demandas/${fx.submeter.id}/editar`);
    await expect(page.getByTestId("montar-demanda")).toBeVisible();
    const resposta = page.waitForResponse((r) => r.url().includes("/submeter/"));
    await page.getByTestId("demanda-submeter").click();
    expect((await resposta).status()).toBe(200);
    await page.waitForURL(`**/sgd/demandas?demanda=${fx.submeter.id}`);

    // Volta pela navegação do app, sem recarregar: o card não pode vir do
    // cache de antes da submissão.
    await page.getByRole("link", { name: "SGP", exact: true }).click();
    await page.getByTestId("sgp-hub-card-meu-saldo").click();
    await expect(card(page)).toBeVisible();
    await expect(card(page).getByTestId("meu-saldo-comprometido")).toContainText("R$ 700,00");
    await expect(card(page).getByTestId("meu-saldo-disponivel")).toContainText("R$ 300,00");
    await expect(card(page)).toHaveAttribute("data-semaforo", "amarelo");

    await card(page).getByTestId("meu-saldo-ver-extrato").click();
    const extrato = page.getByTestId("extrato-tabela");
    const linha = extrato.locator("tr", { has: page.getByTestId("extrato-demanda").filter({ hasText: `#${fx.submeter.id}` }) });
    await expect(linha.getByTestId("extrato-tipo")).toHaveText("Reserva");
    await expect(linha.getByTestId("extrato-valor")).toContainText("700,00");
    await expect(linha.getByTestId("extrato-valor")).toContainText("−");
    await expect(linha.getByTestId("extrato-saldo-depois")).toContainText("R$ 300,00");

    await linha.getByTestId("extrato-demanda").click();
    await expect(page).toHaveURL(new RegExp(`/sgd/demandas\\?demanda=${fx.submeter.id}`));
    await expect(page.getByTestId("demanda-painel")).toContainText(fx.submeter.titulo);
  });

  test("em amarelo, o atalho do recurso extra lista a demanda em rascunho da rubrica", async ({ page }) => {
    await abrir(page);
    await card(page).getByTestId("meu-saldo-recurso-extra").click();

    const painel = page.getByTestId("recurso-extra-atalho-painel");
    await expect(painel).toContainText("Locação de Veículo");
    await expect(painel.getByTestId(`recurso-extra-demanda-${fx.rascunho.id}`)).toContainText(fx.rascunho.titulo);
    // A submetida já não está em Rascunho: não serve para pedir recurso extra.
    await expect(painel.getByTestId(`recurso-extra-demanda-${fx.submeter.id}`)).toHaveCount(0);

    await painel.getByTestId(`recurso-extra-demanda-${fx.rascunho.id}`).click();
    await expect(page).toHaveURL(new RegExp(`/sgd/demandas/${fx.rascunho.id}/editar$`));
  });
});

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("não tem limite: sem card no hub e a tela explica", async ({ page }) => {
    await page.goto("/sgp");
    await expect(page.getByTestId("sgp-hub-card-orcamento")).toBeVisible();
    await expect(page.getByTestId("sgp-hub-card-meu-saldo")).toHaveCount(0);

    await page.goto("/sgp/orcamento/meu-saldo");
    await expect(page.getByText("Sem limite de gasto")).toBeVisible();
  });
});
