import { readFile } from "node:fs/promises";
import { expect, test, type Download, type Page } from "@playwright/test";
import { abrirComApi, apiGet, guardarTarefaDeExportacao } from "./helpers/apiReal";
import { apagarJobsDesde, criarJob, marcoDosJobs } from "./helpers/exportacaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Relatórios do SGP (#239, A4 da #302): o Plano de Trabalho e as Atividades
 * são gerados em segundo plano (`POST /sgp/exportacoes/`) e acompanhados até
 * o download, contra o backend e o worker reais. O job em erro do "Tentar
 * novamente" é um job real do usuário, criado no banco pela fixture.
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

const status = (page: Page, prefixo: "plano" | "atividades") => page.getByTestId(`${prefixo}-exportacao-status`);

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

async function baixar(page: Page, prefixo: "plano" | "atividades"): Promise<Download> {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    status(page, prefixo).getByRole("button", { name: "Baixar arquivo" }).click(),
  ]);
  return download;
}

async function linhasDoCsv(download: Download): Promise<string[]> {
  const texto = (await readFile(await download.path(), "utf8")).replace(/^﻿/, "");
  return texto.split(/\r?\n/).filter((l) => l.trim() !== "");
}

test.describe("SGP — Relatórios (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("card Relatórios aparece na página do SGP com link funcional", async ({ page }) => {
    await page.goto("/sgp");
    const card = page.getByRole("link", { name: /Relatórios/i });
    await expect(card).toBeVisible();
    expect(await card.getAttribute("href")).toContain("/sgp/relatorios");
  });

  test("página de relatórios exibe os dois blocos de exportação", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByRole("heading", { name: "Plano de Trabalho" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Atividades de Campo" })).toBeVisible();
  });

  test("data de fim anterior ao início bloqueia a exportação do PT, sem chamar a API", async ({ page }) => {
    const pedidos: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/v1/sgp/exportacoes/") && r.method() === "POST") pedidos.push(r.url());
    });
    await page.goto("/sgp/relatorios");
    // Botão habilitado = sessão carregada e página hidratada: antes disso o
    // React descarta o que foi digitado.
    await expect(page.getByTestId("plano-exportar")).toBeEnabled();
    await page.getByLabel("Período — início").first().fill("2026-06-10");
    await page.getByLabel("Período — fim").first().fill("2026-06-01");
    await expect(page.getByLabel("Período — início").first()).toHaveValue("2026-06-10");
    await page.getByTestId("plano-exportar").click();
    await expect(page.getByText("O início do período não pode ser posterior ao fim.")).toBeVisible();
    expect(pedidos).toEqual([]);
  });

  test("Plano de Trabalho: gera em segundo plano, acompanha e baixa o arquivo", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByTestId("plano-exportar")).toBeEnabled();
    await escolher(page, "relatorio-pt-formato", /^CSV/);
    const criacao = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/sgp/exportacoes/") && r.request().method() === "POST",
    );
    await page.getByTestId("plano-exportar").click();
    expect((await criacao).status()).toBe(202);

    await expect(status(page, "plano")).toHaveAttribute("data-status", /pendente|processando/);
    await expect(page.getByTestId("plano-exportar")).toBeDisabled();
    await expect(status(page, "plano")).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    await expect(page.getByTestId("plano-exportar")).toBeEnabled();

    const download = await baixar(page, "plano");
    expect(download.suggestedFilename()).toMatch(/^plano_trabalho.*\.csv$/);
    const linhas = await linhasDoCsv(download);
    // O conteúdo é do backend (`workplan_export`): aqui basta ser o arquivo do PT.
    for (const coluna of ["Meta", "Ação", "Semáforo"]) expect(linhas[0].split(",")).toContain(coluna);
    expect(linhas.length).toBeGreaterThan(1);
  });

  test("Atividades com período, território e ação: o job leva os filtros e o arquivo sai", async ({ page }) => {
    const origem = await abrirComApi(page, "/sgp/relatorios");
    await expect(page.getByTestId("atividades-exportar")).toBeEnabled();
    await escolher(page, "relatorio-at-formato", /^CSV/);
    await page.getByLabel("Período — início").nth(1).fill("2020-01-01");
    await page.getByLabel("Período — fim").nth(1).fill("2030-12-31");
    await expect(page.getByLabel("Período — início").nth(1)).toHaveValue("2020-01-01");
    await escolher(page, "relatorio-at-territorio", /./);
    await escolher(page, "relatorio-at-acao", /./);

    const criacao = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/sgp/exportacoes/") && r.request().method() === "POST",
    );
    await page.getByTestId("atividades-exportar").click();
    const job = (await (await criacao).json()) as { id: number };

    await expect(status(page, "atividades")).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    // O backend gravou os quatro filtros do contrato do `AtividadesExportQuerySerializer`.
    const gravado = await apiGet<{ tipo: string; filtros: Record<string, unknown> }>(
      page,
      origem,
      `/api/v1/sgp/exportacoes/${job.id}/`,
    );
    expect(gravado.tipo).toBe("atividades");
    expect(Object.keys(gravado.filtros).sort()).toEqual(["acao_id", "periodo_fim", "periodo_inicio", "territorio_id"]);

    const download = await baixar(page, "atividades");
    expect(download.suggestedFilename()).toMatch(/^atividades.*\.csv$/);
    expect((await linhasDoCsv(download)).length).toBeGreaterThanOrEqual(1);
  });

  test("sair e voltar à página retoma a exportação em andamento", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByTestId("plano-exportar")).toBeEnabled();
    await page.getByTestId("plano-exportar").click();
    await expect(status(page, "plano")).toBeVisible();
    await page.goto("/sgp");
    await page.goto("/sgp/relatorios");
    await expect(status(page, "plano")).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    expect((await baixar(page, "plano")).suggestedFilename()).toMatch(/^plano_trabalho/);
  });

  test("job em erro: mostra a mensagem e 'Tentar novamente' reenfileira", async ({ page }) => {
    const id = criarJob(UGP, "atividades", "erro");
    const origem = await abrirComApi(page, "/sgp/relatorios");
    await guardarTarefaDeExportacao(page, origem, "sgp.relatorios.atividades", id, { formato: "csv" });
    await page.reload();

    await expect(status(page, "atividades")).toHaveAttribute("data-status", "erro");
    await expect(status(page, "atividades")).toContainText("O worker não conseguiu gerar o arquivo.");
    const repetir = page.waitForResponse((r) => r.url().endsWith(`/api/v1/sgp/exportacoes/${id}/repetir/`));
    await status(page, "atividades").getByRole("button", { name: "Tentar novamente" }).click();
    expect((await repetir).status()).toBe(202);
    await expect(status(page, "atividades")).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
  });
});

test.describe("SGP — Relatórios (Super Admin)", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("super admin vê o bloco de integração Power BI", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByRole("heading", { name: /Power BI/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /Gerenciar integração/i })).toBeVisible();
  });
});

test.describe("SGP — Relatórios (ADT)", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("ADT não vê o bloco Power BI", async ({ page }) => {
    await page.goto("/sgp/relatorios");
    await expect(page.getByRole("heading", { name: /Power BI/i })).toHaveCount(0);
  });
});

test.describe("SGP — Relatórios (Articulador Estadual)", () => {
  // O backend exporta o recorte dos estados do Articulador (`resolver_escopo`).
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("o Articulador vê o card e exporta", async ({ page }) => {
    await page.goto("/sgp");
    await expect(page.getByTestId("sgp-hub-card-relatorios")).toBeVisible();
    await page.goto("/sgp/relatorios");
    await expect(page.getByTestId("plano-exportar")).toBeEnabled();
    await expect(page.getByTestId("atividades-exportar")).toBeEnabled();
  });
});

test.describe("SGP — Relatórios (sem permissão de exportar)", () => {
  // A FGD não tem papel com escopo no SGP: o backend nega a exportação.
  test.use({ storageState: storageStatePath("fgd") });

  test("a FGD não vê o card no hub e a página mostra o acesso restrito", async ({ page }) => {
    await page.goto("/sgp");
    await expect(page.getByTestId("sgp-hub-card-painel")).toBeVisible();
    await expect(page.getByTestId("sgp-hub-card-relatorios")).toHaveCount(0);

    await page.goto("/sgp/relatorios");
    await expect(page.getByText("Conteúdo restrito")).toBeVisible();
    await expect(page.getByTestId("plano-exportar")).toHaveCount(0);
    await expect(page.getByTestId("atividades-exportar")).toHaveCount(0);
  });
});
