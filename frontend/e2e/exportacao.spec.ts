import { readFile } from "node:fs/promises";
import { expect, test, type Download, type Page } from "@playwright/test";
import { abrirComApi, guardarTarefaDeExportacao } from "./helpers/apiReal";
import { apagarJobsDesde, criarJob, marcoDosJobs } from "./helpers/exportacaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Exportação do Plano de Trabalho pelo painel (#142, A4 da #302).
 *
 * O arquivo é gerado em segundo plano pelo worker (`POST /sgp/exportacoes/`,
 * tipo `plano_trabalho`) e acompanhado no próprio modal até o download, contra
 * o backend real. O conteúdo do dataset tem cobertura própria no backend
 * (`test_workplan_exports.py`); aqui a tela entrega os filtros, acompanha o job
 * e baixa o arquivo certo.
 */

test.describe.configure({ mode: "serial" });

const UGP = "beatriz.nogueira@demo.pdhc.local";

let marco: number;

test.beforeAll(() => {
  marco = marcoDosJobs();
});

test.afterAll(() => {
  apagarJobsDesde(marco);
});

const status = (page: Page) => page.getByTestId("exportar-exportacao-status");

async function abrirModal(page: Page): Promise<void> {
  await page.goto("/sgp/painel");
  await expect(page.getByTestId("painel-page")).toBeVisible();
  await page.getByTestId("painel-exportar-btn").click();
  await expect(page.getByTestId("exportar-modal")).toBeVisible();
}

/** Escolhe uma opção num <Select> do design system pelo texto. */
async function escolher(page: Page, testId: string, texto: RegExp): Promise<void> {
  const campo = page.getByTestId(testId);
  await campo.locator('button[role="combobox"]').click();
  await campo.locator('li[role="option"]').filter({ hasText: texto }).click();
}

/** Confirma, espera o worker concluir e baixa pelo botão do modal. */
async function exportarEBaixar(page: Page): Promise<Download> {
  const criacao = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/sgp/exportacoes/") && r.request().method() === "POST",
  );
  await page.getByTestId("exportar-confirmar").click();
  expect((await criacao).status()).toBe(202);
  await expect(status(page)).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    status(page).getByRole("button", { name: "Baixar arquivo" }).click(),
  ]);
  return download;
}

/** Uma linha de CSV em células, respeitando aspas. */
function celulas(linha: string): string[] {
  const saida: string[] = [];
  let atual = "";
  let entreAspas = false;
  for (let i = 0; i < linha.length; i++) {
    const c = linha[i];
    if (c === '"' && linha[i + 1] === '"' && entreAspas) {
      atual += '"';
      i++;
    } else if (c === '"') {
      entreAspas = !entreAspas;
    } else if (c === "," && !entreAspas) {
      saida.push(atual);
      atual = "";
    } else {
      atual += c;
    }
  }
  saida.push(atual);
  return saida;
}

test.describe("Exportação do Plano de Trabalho — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("CSV filtrando uma Meta: o arquivo só traz aquela Meta", async ({ page }) => {
    await abrirModal(page);
    await escolher(page, "exportar-formato", /^CSV/);
    await escolher(page, "exportar-meta", /^Meta 1 /);

    const download = await exportarEBaixar(page);
    expect(download.suggestedFilename()).toMatch(/^plano_trabalho.*\.csv$/);

    // O backend prefixa BOM para o Excel abrir os acentos corretamente.
    const conteudo = (await readFile(await download.path(), "utf8")).replace(/^﻿/, "");
    const [cabecalho, ...linhas] = conteudo.split(/\r?\n/).filter((l) => l !== "");
    const colunaMeta = celulas(cabecalho).indexOf("Meta");
    expect(colunaMeta).toBeGreaterThanOrEqual(0);
    expect(linhas.length).toBeGreaterThan(0);
    // A coluna Meta sai como `{numero} - {titulo}`.
    for (const linha of linhas) expect(celulas(linha)[colunaMeta]).toMatch(/^1 - /);
  });

  test("Excel baixa um .xlsx válido", async ({ page }) => {
    await abrirModal(page);
    await escolher(page, "exportar-formato", /^Excel/);

    const download = await exportarEBaixar(page);
    expect(download.suggestedFilename()).toMatch(/^plano_trabalho.*\.xlsx$/);

    // Um .xlsx é um zip do OOXML: assinatura PK, o manifesto de tipos e ao
    // menos uma planilha. Validar as células é trabalho do teste do backend.
    const bytes = await readFile(await download.path());
    expect(bytes.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]));
    const bruto = bytes.toString("latin1");
    expect(bruto).toContain("[Content_Types].xml");
    expect(bruto).toContain("xl/worksheets/");
  });

  test("com um job em andamento, o modal mostra o andamento e não deixa pedir outro", async ({ page }) => {
    // Job pendente real, fora da fila: fica parado o tempo que o teste precisa.
    const id = criarJob(UGP, "plano_trabalho", "pendente");
    const origem = await abrirComApi(page, "/sgp/painel");
    await guardarTarefaDeExportacao(page, origem, "sgp.painel.plano-trabalho", id, { formato: "csv" });
    await page.reload();
    await expect(page.getByTestId("painel-page")).toBeVisible();
    await page.getByTestId("painel-exportar-btn").click();

    await expect(status(page)).toHaveAttribute("data-status", "pendente");
    await expect(status(page)).toContainText("na fila");
    await expect(page.getByTestId("exportar-confirmar")).toBeDisabled();
  });

  test("fechar o modal não perde a exportação: ela reaparece ao reabrir", async ({ page }) => {
    await abrirModal(page);
    const criacao = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/sgp/exportacoes/") && r.request().method() === "POST",
    );
    await page.getByTestId("exportar-confirmar").click();
    expect((await criacao).status()).toBe(202);

    await page.getByTestId("exportar-cancelar").click();
    await expect(page.getByTestId("exportar-modal")).toBeHidden();
    await page.getByTestId("painel-exportar-btn").click();
    await expect(status(page)).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    await expect(page.getByTestId("exportar-confirmar")).toBeEnabled();
  });
});

test.describe("Exportação do Plano de Trabalho — FGD", () => {
  // O painel é aberto a qualquer autenticado, mas a exportação segue o escopo
  // do SGP, que a FGD não tem (403 no `POST /sgp/exportacoes/`).
  test.use({ storageState: storageStatePath("fgd") });

  test("a FGD vê o painel sem o botão Exportar", async ({ page }) => {
    await page.goto("/sgp/painel");
    await expect(page.getByTestId("painel-page")).toBeVisible();
    await expect(page.getByTestId("painel-exportar-btn")).toHaveCount(0);
  });
});
