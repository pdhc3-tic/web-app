import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import {
  criarArloFixture,
  planilhaDeRetorno,
  PREFIXO_298,
  removerArloFixture,
  type ArloFixture,
} from "./helpers/arloFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Integração Arlo (#298 · SGD-FE-5) contra o backend real (BE-4, PR #330).
 *
 * A importação roda numa task do Celery: os testes esperam a operação sair de
 * Pendente/Processando antes de conferir o resultado.
 */

let fx: ArloFixture;

async function importar(page: Page, nome: string, conteudo: Buffer) {
  await page.getByTestId("arlo-arquivo").setInputFiles({ name: nome, mimeType: "text/csv", buffer: conteudo });
  await page.getByTestId("arlo-importar").getByRole("button", { name: "Importar", exact: true }).click();
  const acompanhamento = page.getByTestId("arlo-acompanhamento");
  await expect(acompanhamento.getByRole("button", { name: "Importar outra planilha" })).toBeVisible({
    timeout: 60_000,
  });
  return acompanhamento;
}

test.describe("Integração Arlo — FGD", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: storageStatePath("fgd") });

  test.beforeAll(() => {
    fx = criarArloFixture();
  });
  test.afterAll(() => {
    if (fx) removerArloFixture(fx.ultimaOperacao);
  });

  test("o card do SGD leva à tela, que lista as demandas autorizadas", async ({ page }) => {
    await page.goto("/sgd");
    await page.getByTestId("sgd-arlo").click();
    await expect(page).toHaveURL(/\/sgd\/arlo\/?$/);

    const autorizadas = page.getByTestId("arlo-autorizadas");
    await expect(autorizadas.getByText(fx.paga.titulo)).toBeVisible();
    await expect(autorizadas.getByText(fx.glosa.titulo)).toBeVisible();
  });

  test("exportar gera o download do CSV com as demandas autorizadas e registra no histórico", async ({
    page,
  }) => {
    await page.goto("/sgd/arlo");
    await expect(page.getByTestId("arlo-autorizadas")).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Exportar para Arlo" }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.csv$/);
    const csv = readFileSync(await download.path(), "utf8");
    const [cabecalho, ...linhas] = csv.trim().split(/\r?\n/);
    expect(cabecalho).toContain("ID Demanda");
    expect(linhas.some((l) => l.includes(fx.paga.titulo))).toBe(true);
    expect(linhas.some((l) => l.includes(fx.glosa.titulo))).toBe(true);

    await expect(page.getByText(/Download de .+\.csv iniciado\./)).toBeVisible();
    const historico = page.getByTestId("arlo-historico");
    await expect(historico.locator("tbody tr").first()).toContainText("Exportação");
  });

  test("importar uma planilha válida paga a demanda e confirma", async ({ page }) => {
    await page.goto("/sgd/arlo");
    const acompanhamento = await importar(
      page,
      `${PREFIXO_298}-retorno.csv`,
      planilhaDeRetorno([{ demanda: fx.paga.id, solicitacao: fx.paga.solicitacaoId, valorPago: "1200,00" }]),
    );

    await expect(acompanhamento).toContainText("Concluído");
    await expect(page.getByTestId("arlo-resumo")).toContainText("1 de 1 linha processada");
    await expect(page.getByText("Importação concluída. As demandas pagas foram atualizadas.")).toBeVisible();
    // Paga, a demanda deixa de ser Autorizada e sai da lista de exportação.
    await expect(page.getByTestId("arlo-autorizadas").getByText(fx.paga.titulo)).toHaveCount(0);
  });

  test("linha malformada mostra o erro daquela linha sem impedir as demais", async ({ page }) => {
    await page.goto("/sgd/arlo");
    await importar(
      page,
      `${PREFIXO_298}-retorno-com-erro.csv`,
      planilhaDeRetorno([
        { demanda: fx.glosa.id, solicitacao: fx.glosa.solicitacaoId, valorPago: "1500,00" },
        { demanda: fx.glosa.id, solicitacao: fx.glosa.solicitacaoId, valorPago: "R$ abc" },
      ]),
    );

    await expect(page.getByTestId("arlo-resumo")).toContainText("1 de 2 linhas processadas");
    await expect(page.getByTestId("arlo-resumo")).toContainText("1 linha recusada");
    const erros = page.getByTestId("arlo-erros");
    await expect(erros.getByRole("row").filter({ hasText: "Valor pago em formato inválido" })).toHaveCount(1);
    await expect(erros.getByRole("row").filter({ hasText: "Valor Pago" })).toHaveCount(1);
  });

  test("o histórico abre o detalhe da importação com os erros por linha", async ({ page }) => {
    await page.goto("/sgd/arlo");
    const linha = page
      .getByTestId("arlo-historico")
      .locator("tbody tr")
      .filter({ hasText: `${PREFIXO_298}-retorno-com-erro.csv` });
    await expect(linha).toContainText("1/2");
    await expect(linha).toContainText("1 erro");
    await linha.click();

    const detalhe = page.getByTestId("arlo-operacao-detalhe");
    await expect(detalhe).toContainText("Adriano");
    await expect(detalhe.getByTestId("arlo-erros")).toContainText("Valor pago em formato inválido");
  });

  // Pendência de backend (docs/pendencias-backend-sprint-10.md): o risco de
  // glosa é gravado na importação (`GlosaRisk`), mas nenhum endpoint o devolve.
  test.fixme("demanda paga acima do autorizado aparece destacada como risco de glosa", async () => {});
});

test.describe("Integração Arlo — acesso", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("fora de FGD e Super Admin a tela é restrita e o card não aparece", async ({ page }) => {
    await page.goto("/sgd");
    await expect(page.getByTestId("sgd-painel")).toBeVisible();
    await expect(page.getByTestId("sgd-arlo")).toHaveCount(0);

    await page.goto("/sgd/arlo");
    await expect(page.locator("main").getByRole("alert")).toContainText("Disponível para FGD e Super Admin");
    await expect(page.getByTestId("arlo-exportar")).toHaveCount(0);
  });
});
