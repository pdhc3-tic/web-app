import { expect, test, type Page } from "@playwright/test";
import {
  criarDiariasSemValorFixture,
  FAIXA_NOME,
  removerDiariasSemValorFixture,
  type DiariasSemValorFixture,
} from "./helpers/diariasSemValorFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Diária sem valor vigente (#440), contra o backend real. Sem valor na tabela
 * para a faixa do destino, o backend recusa o cálculo (#439); o front avisa e
 * não deixa salvar, e o Super Admin vê a faixa sem valor na Tabela de diárias
 * e no hub de Configurações.
 *
 * Serial: o último passo cadastra o valor pela tela e confere que o formulário
 * volta a calcular. A fixture cria uma faixa própria, sem mexer nas outras.
 */

let fx: DiariasSemValorFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarDiariasSemValorFixture();
});

test.afterAll(() => {
  removerDiariasSemValorFixture();
});

/** `AAAA-MM-DD` daqui a `dias` dias. */
function diaIso(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

/** Abre a nova solicitação de Diárias com o destino da faixa sem valor. */
async function abrirDiaria(page: Page) {
  await page.goto(`/sgd/demandas/${fx.demandaId}/editar`);
  await expect(page.getByTestId("montar-demanda")).toBeVisible();
  await page.getByTestId("solicitacao-adicionar").click();
  const form = page.getByTestId("solicitacao-form");
  await escolher(page, "solicitacao-tipo", "Diárias");
  await page.getByTestId("campo-municipio_destino_id").fill(fx.municipioNome);
  await page.getByRole("option", { name: fx.municipioNome, exact: true }).click();
  await form.getByLabel("Data de ida").fill(diaIso(30));
  await form.getByLabel("Data de volta").fill(diaIso(32));
  return form;
}

test.describe("ADT sem valor na tabela", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o formulário avisa e não deixa salvar a diária", async ({ page }) => {
    await abrirDiaria(page);

    const erro = page.getByTestId("simulacao-diarias-erro");
    await expect(erro).toContainText(`Sem valor de diária vigente para a faixa '${FAIXA_NOME}'`);
    await expect(page.getByTestId("simulacao-diarias-bloqueio")).toContainText("não pode ser salva");
    await expect(page.getByTestId("simulacao-diarias-total")).toHaveCount(0);
    await expect(page.getByTestId("solicitacao-salvar")).toBeDisabled();
    await expect(page.getByTestId("solicitacao-bloqueio")).toBeVisible();
  });
});

test.describe("Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("o hub de Configurações avisa no card da Tabela de diárias", async ({ page }) => {
    await page.goto("/admin/configuracoes");
    await expect(page.getByTestId("configuracao-aviso-diarias")).toContainText("sem valor vigente");
  });

  test("a Tabela de diárias destaca a faixa e o destaque some ao cadastrar o valor", async ({ page }) => {
    await page.goto("/admin/configuracoes/sgd/diarias");
    await expect(page.getByTestId("diarias-aviso-lacunas")).toContainText(FAIXA_NOME);
    const selo = page.getByTestId(`grade-lacuna-${fx.faixaId}`);
    await expect(selo).toHaveText("Sem valor vigente");

    await page.getByTestId(`grade-editar-${fx.faixaId}`).click();
    const form = page.getByTestId("valor-diaria-form");
    await form.getByLabel(/valor da diária/i).fill("40000");
    await form.getByLabel(/Início/).fill(diaIso(0));
    await escolher(page, "valor-diaria-origem", "Valor FGD");
    await page.getByTestId("valor-diaria-salvar").click();
    await expect(form).toHaveCount(0);

    await expect(selo).toHaveCount(0);
    await expect(page.getByTestId(`grade-faixa-${fx.faixaId}`)).toContainText("R$ 400,00");
  });
});

test.describe("ADT depois do cadastro", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o formulário volta a calcular e permite salvar", async ({ page }) => {
    await abrirDiaria(page);

    await expect(page.getByTestId("simulacao-diarias-total")).toContainText("R$");
    await expect(page.getByTestId("simulacao-diarias-erro")).toHaveCount(0);
    await expect(page.getByTestId("solicitacao-salvar")).toBeEnabled();
  });
});
