import { expect, test, type Page } from "@playwright/test";
import {
  comprometerOrigem,
  criarRemanejamentoPoolsFixture,
  lerAlocado,
  reiniciarPools,
  removerRemanejamentoPoolsFixture,
  type RemanejamentoPoolsFixture,
} from "./helpers/remanejamentoPoolsFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #402 (AJ-FE-06) — Simulador de remanejamento entre pools, contra o backend
 * real. A UGP escolhe origem e destino da mesma rubrica, simula, vê o antes e
 * depois com a mudança de faixa e confirma com o mesmo payload. Quando o saldo
 * da origem muda entre a simulação e a confirmação, o backend recusa com
 * `INSUFFICIENT_BALANCE` e a tela pede nova simulação.
 *
 * O payload enviado é lido das requisições, sem interceptá-las.
 */

let fx: RemanejamentoPoolsFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarRemanejamentoPoolsFixture();
});

test.afterAll(() => {
  removerRemanejamentoPoolsFixture();
});

const SIMULAR = "/api/v1/sgp/orcamento/remanejamentos/simular/";
const CONFIRMAR = "/api/v1/sgp/orcamento/remanejamentos/";

const opcao = (territorio: string, rubrica = "Diárias") =>
  new RegExp(`^${territorio} · ${rubrica} · saldo`);

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, nome: RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: nome }).first().click();
}

async function preencher(page: Page, valor = "1000") {
  await page.goto("/sgp/orcamento/remanejamentos/novo");
  await expect(page.getByTestId("remanejamento-form")).toBeVisible();
  await escolher(page, "remanejamento-origem", opcao(fx.origem.territorio));
  await escolher(page, "remanejamento-destino", opcao(fx.destino.territorio));
  await page.getByLabel("Valor (R$)").fill(valor);
  await page.getByLabel("Justificativa").fill("Reforço para o território com o pool no vermelho.");
}

/** Corpos dos POST de simulação e de confirmação, na ordem em que saíram. */
function capturarPayloads(page: Page) {
  const corpos = { simular: [] as unknown[], confirmar: [] as unknown[] };
  page.on("request", (req) => {
    if (req.method() !== "POST") return;
    const url = new URL(req.url()).pathname;
    if (url.endsWith(SIMULAR)) corpos.simular.push(req.postDataJSON());
    else if (url.endsWith(CONFIRMAR)) corpos.confirmar.push(req.postDataJSON());
  });
  return corpos;
}

test.describe("UGP — novo remanejamento", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.beforeEach(() => {
    reiniciarPools();
  });

  test("chega pelo Painel de Orçamento", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await page.getByTestId("orcamento-ir-remanejamento").click();
    await expect(page).toHaveURL(/\/sgp\/orcamento\/remanejamentos\/novo$/);
    await expect(page.getByTestId("remanejamento-form")).toBeVisible();
  });

  test("o destino só oferece pools da rubrica da origem", async ({ page }) => {
    await page.goto("/sgp/orcamento/remanejamentos/novo");
    await expect(page.locator("button#remanejamento-destino")).toBeDisabled();

    await escolher(page, "remanejamento-origem", opcao(fx.origem.territorio));
    await page.locator("button#remanejamento-destino").click();
    await expect(page.getByRole("option", { name: opcao(fx.destino.territorio) })).toBeVisible();
    await expect(
      page.getByRole("option", { name: opcao(fx.outraRubrica.territorio, "Material gráfico") }),
    ).toHaveCount(0);
    await expect(page.getByText(/Só pools de Diárias, a rubrica da origem/)).toBeVisible();
  });

  test("simula, vê o antes e depois com a mudança de faixa e confirma com o mesmo payload", async ({ page }) => {
    const corpos = capturarPayloads(page);
    await preencher(page);
    await expect(page.getByTestId("remanejamento-confirmar")).toHaveCount(0);

    await page.getByTestId("remanejamento-simular").click();
    await expect(page.getByTestId("remanejamento-simulacao")).toBeVisible();
    await expect(page.getByTestId("impacto-origem-saldo-antes")).toContainText("10.000,00");
    await expect(page.getByTestId("impacto-origem-saldo-depois")).toContainText("9.000,00");
    await expect(page.getByTestId("impacto-destino-saldo-antes")).toContainText("50,00");
    await expect(page.getByTestId("impacto-destino-saldo-depois")).toContainText("1.050,00");
    // 95% comprometido (vermelho) → 47,5% (verde).
    await expect(page.getByTestId("impacto-destino-mudou-faixa")).toBeVisible();
    await expect(page.getByTestId("impacto-origem-mudou-faixa")).toHaveCount(0);

    await page.getByTestId("remanejamento-confirmar").click();
    await expect(page).toHaveURL(/\/sgp\/orcamento$/);

    expect(corpos.confirmar).toHaveLength(1);
    expect(corpos.confirmar[0]).toEqual(corpos.simular.at(-1));
    expect(lerAlocado(fx)).toEqual({ origem: "9000.00", destino: "2000.00" });
  });

  test("mudar um campo depois de simular descarta a simulação", async ({ page }) => {
    await preencher(page);
    await page.getByTestId("remanejamento-simular").click();
    await expect(page.getByTestId("remanejamento-confirmar")).toBeEnabled();

    await page.getByLabel("Valor (R$)").fill("2000");
    await expect(page.getByTestId("remanejamento-simulacao")).toHaveCount(0);
  });

  test("valor acima do saldo é recusado já na simulação, com o saldo da origem", async ({ page }) => {
    await preencher(page, "20000");
    await page.getByTestId("remanejamento-simular").click();

    const erro = page.getByTestId("remanejamento-erro");
    await expect(erro).toContainText("O valor passa do saldo da origem: há R$ 10.000,00 disponível");
    await expect(erro).not.toContainText("INSUFFICIENT_BALANCE");
    await expect(page.getByTestId("remanejamento-simulacao")).toHaveCount(0);
  });

  test("saldo que muda depois da simulação é recusado na confirmação e as opções se atualizam", async ({ page }) => {
    await preencher(page);
    await page.getByTestId("remanejamento-simular").click();
    await expect(page.getByTestId("remanejamento-confirmar")).toBeEnabled();

    // Outra operação consome a origem: sobram R$ 500.
    comprometerOrigem(fx, "500.00");
    await page.getByTestId("remanejamento-confirmar").click();

    const erro = page.getByTestId("remanejamento-erro");
    await expect(erro).toContainText("O saldo da origem mudou desde a simulação e agora é R$ 500,00");
    await expect(erro).not.toContainText("INSUFFICIENT_BALANCE");
    await expect(page.getByTestId("remanejamento-simulacao")).toHaveCount(0);
    expect(lerAlocado(fx)).toEqual({ origem: "10000.00", destino: "1000.00" });

    await page.locator("button#remanejamento-origem").click();
    await expect(
      page.getByRole("option", { name: new RegExp(`^${fx.origem.territorio} · Diárias · saldo R\\$\\s500,00`) }),
    ).toBeVisible();
  });
});

test.describe("ADT", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("não acessa o remanejamento", async ({ page }) => {
    await page.goto("/sgp/orcamento/remanejamentos/novo");
    await expect(page.getByText(/O remanejamento entre pools é da UGP e do Super Admin/)).toBeVisible();
    await expect(page.getByTestId("remanejamento-form")).toHaveCount(0);
  });
});
