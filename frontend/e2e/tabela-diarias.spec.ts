import { expect, test, type Page } from "@playwright/test";
import {
  criarDiariasFixture,
  lerEstadoDiarias,
  removerDiariasFixture,
  type DiariasFixture,
} from "./helpers/diariasFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #366 (SGD-REF-FE-08) — Tabela de diárias contra o backend real
 * (`/api/v1/sgd/config/diarias/`), com as faixas e os valores da carga inicial
 * (migration `0023_seed_faixas_diarias`).
 *
 * As gravações (nova vigência, municípios da faixa e parâmetros) mudam o
 * cálculo das diárias das outras specs: a fixture fotografa a configuração e
 * a restaura no fim (`diariasFixture.ts`).
 */

const TELA = "/admin/configuracoes/sgd/diarias";

test.describe.configure({ mode: "serial" });

/** `AAAA-MM-DD` daqui a `dias`, no fuso local, como o `<input type="date">`. */
function diaIso(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const brasileira = (iso: string) => iso.split("-").reverse().join("/");

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

test.describe("Tabela de diárias — gravações da FGD", () => {
  test.use({ storageState: storageStatePath("fgd") });

  let fx: DiariasFixture;

  test.beforeAll(() => {
    fx = criarDiariasFixture();
  });

  test.afterAll(() => {
    removerDiariasFixture();
  });

  test("a nova vigência encerra a atual na véspera, e excluí-la reabre a anterior", async ({ page }) => {
    const inicio = diaIso(40);
    const vespera = diaIso(39);
    const faixa = fx.faixaDemais;

    await page.goto(TELA);
    await page.getByTestId(`grade-editar-${faixa.id}`).click();
    const form = page.getByTestId("valor-diaria-form");
    await expect(form.getByTestId("valor-diaria-atual")).toContainText("R$ 300,00");
    await form.getByLabel(/Novo valor da diária/).fill("35000");
    await form.getByLabel(/Início da nova vigência/).fill(inicio);
    await escolher(page, "valor-diaria-origem", /^Federal/);

    const edicao = page.waitForResponse(
      (r) => new URL(r.url()).pathname.endsWith(`/sgd/config/diarias/tabela/${fx.valorDemais.id}/`) && r.request().method() === "PATCH",
    );
    await page.getByTestId("valor-diaria-salvar").click();
    expect((await edicao).status()).toBe(201);
    await expect(form).toHaveCount(0);

    // No banco: a vigência atual termina na véspera, e a nova começa na data pedida.
    const depois = lerEstadoDiarias().valoresDemais;
    expect(depois).toHaveLength(2);
    const [antiga, nova] = depois;
    expect(antiga).toMatchObject({ id: fx.valorDemais.id, fim: vespera, valor: fx.valorDemais.valor });
    expect(nova).toMatchObject({ inicio, fim: null, valor: "350.00", origem: "federal" });

    // Na grade: uma coluna nova, com o valor e a origem.
    const grade = page.getByTestId("grade-diarias");
    await expect(grade.getByRole("columnheader", { name: `A partir de ${brasileira(inicio)}` })).toBeVisible();
    const linha = page.getByTestId(`grade-faixa-${faixa.id}`);
    await expect(linha).toContainText("R$ 350,00");
    await expect(linha).toContainText("Federal");

    // No histórico, a nova ainda não vigora e é a única que pode sair.
    await page.getByTestId(`grade-historico-${faixa.id}`).click();
    await expect(page.getByTestId(`historico-valor-${nova.id}`)).toContainText("Ainda não vigora");
    await expect(page.getByTestId(`historico-valor-${antiga.id}`)).toContainText("Vigente");
    await expect(page.getByTestId(`historico-excluir-${antiga.id}`)).toHaveCount(0);

    const exclusao = page.waitForResponse(
      (r) => new URL(r.url()).pathname.endsWith(`/sgd/config/diarias/tabela/${nova.id}/`) && r.request().method() === "DELETE",
    );
    await page.getByTestId(`historico-excluir-${nova.id}`).click();
    await page.getByRole("button", { name: "Confirmar" }).click();
    expect((await exclusao).status()).toBe(204);

    expect(lerEstadoDiarias().valoresDemais).toEqual([{ ...antiga, fim: null }]);
    await expect(grade.getByRole("columnheader", { name: `A partir de ${brasileira(inicio)}` })).toHaveCount(0);
  });

  test("os municípios da faixa são gravados ao adicionar e ao remover", async ({ page }) => {
    const faixa = fx.faixaListada;
    const { nome, codigoIbge } = fx.municipioLivre;
    const antes = lerEstadoDiarias().municipiosListada;
    expect(antes).not.toContain(codigoIbge);

    await page.goto(TELA);
    const bloco = page.getByTestId(`faixa-municipios-${faixa.id}`);
    await bloco.getByTestId(`faixa-${faixa.id}-adicionar`).fill(nome);
    await page.getByRole("option", { name: nome, exact: true }).click();
    await expect(bloco.getByTestId(`faixa-${faixa.id}-municipio-${codigoIbge}`)).toBeVisible();

    const salvarFaixa = () =>
      page.waitForResponse(
        (r) => new URL(r.url()).pathname.endsWith(`/sgd/config/diarias/faixas/${faixa.id}/`) && r.request().method() === "PATCH",
      );
    let gravacao = salvarFaixa();
    await bloco.getByTestId(`faixa-${faixa.id}-salvar`).click();
    expect((await gravacao).status()).toBe(200);
    expect(lerEstadoDiarias().municipiosListada).toEqual([...antes, codigoIbge].sort());

    await page
      .getByTestId(`faixa-municipios-${faixa.id}`)
      .getByRole("button", { name: `Remover ${nome} de ${faixa.nome}` })
      .click();
    gravacao = salvarFaixa();
    await page.getByTestId(`faixa-${faixa.id}-salvar`).click();
    expect((await gravacao).status()).toBe(200);
    expect(lerEstadoDiarias().municipiosListada).toEqual(antes);
    await expect(page.getByTestId(`faixa-${faixa.id}-municipio-${codigoIbge}`)).toHaveCount(0);
  });

  test("os parâmetros de contagem são gravados no Core", async ({ page }) => {
    expect(lerEstadoDiarias().parametros.sgd_diaria_regra_meia_no_retorno).toBe("True");

    await page.goto(TELA);
    const salvar = page.getByTestId("parametros-diarias-salvar");
    await expect(salvar).toBeDisabled();
    await page.getByTestId("parametro-regra_meia_no_retorno").uncheck();
    await expect(salvar).toBeEnabled();

    const gravacao = page.waitForResponse(
      (r) => new URL(r.url()).pathname.endsWith("/sgd/config/diarias/parametros/") && r.request().method() === "PATCH",
    );
    await salvar.click();
    expect((await gravacao).status()).toBe(200);
    expect(lerEstadoDiarias().parametros.sgd_diaria_regra_meia_no_retorno).toBe("False");

    // A tela passa a refletir o que foi gravado: nada mais a salvar.
    await expect(page.getByTestId("parametro-regra_meia_no_retorno")).not.toBeChecked();
    await expect(page.getByTestId("parametros-diarias-salvar")).toBeDisabled();
  });
});

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
