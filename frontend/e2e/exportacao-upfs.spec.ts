import { readFile } from "node:fs/promises";
import { expect, test, type Download, type Page } from "@playwright/test";
import { abrirComApi, guardarTarefaDeExportacao } from "./helpers/apiReal";
import {
  apagarJob,
  apagarJobsDesde,
  criarJob,
  criarUpfsEmVolume,
  marcoDosJobs,
  removerUpfsEmVolume,
} from "./helpers/exportacaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #240 — Exportação da listagem de UPFs.
 *
 * Duas partes:
 *
 * 1. **Backend real** (`GET /api/v1/upfs/exportar/`, PR #306): o download
 *    síncrono, a igualdade entre arquivo e listagem, o CPF por perfil, o
 *    recorte territorial e o 400 de filtro inválido.
 *
 * 2. **Exportação em segundo plano, também contra o backend real.** Acima do
 *    limite do backend (`UPF_EXPORT_ASYNC_THRESHOLD`, 1.000 por padrão) ele
 *    responde 202 e o worker gera o arquivo. A fixture cria 1.001 UPFs para a
 *    listagem passar do limite; os estados que o fluxo normal não segura por
 *    tempo bastante (erro, job removido, arquivo vencido) são jobs reais do
 *    usuário criados no banco. Só o 500 do servidor é forçado.
 */

test.describe.configure({ mode: "serial" });

const UGP = "beatriz.nogueira@demo.pdhc.local";
const CHAVE_TAREFA = "sgp.upfs.exportacao";

const COLUNAS = "Estado,Município,Território,Comunidade,Titular,CPF,Data de cadastro";

const statusPanel = (page: Page) => page.getByTestId("upfs-exportacao-status");
const botaoExportar = (page: Page) => page.getByRole("button", { name: "Exportar" });

/** Linhas de dados do CSV baixado (sem o BOM e sem o cabeçalho). */
async function linhasDoCsv(download: Download): Promise<{ cabecalho: string; linhas: string[] }> {
  const texto = (await readFile(await download.path(), "utf8")).replace(/^﻿/, "");
  const [cabecalho, ...resto] = texto.split(/\r?\n/);
  return { cabecalho, linhas: resto.filter((l) => l.trim() !== "") };
}

/** Exporta e devolve o download junto com o `count` da listagem que a tela mostrava. */
async function exportarComListagem(page: Page, url: string) {
  const listagem = page.waitForResponse(
    (r) => /\/api\/v1\/upfs\/\?/.test(r.url()) && r.request().method() === "GET",
  );
  await page.goto(url);
  const resposta = await listagem;
  const { count } = (await resposta.json()) as { count: number };

  const pedidoExport = page.waitForRequest((r) => r.url().includes("/api/v1/upfs/exportar/"));
  const [download] = await Promise.all([page.waitForEvent("download"), botaoExportar(page).click()]);
  return { download, count, urlListagem: resposta.url(), urlExport: (await pedidoExport).url() };
}

/** Parâmetros de filtro de uma URL (sem paginação, ordenação e formato). */
function filtrosDe(url: string): Record<string, string> {
  const fora = new Set(["limit", "offset", "ordering", "formato"]);
  const out: Record<string, string> = {};
  for (const [k, v] of new URL(url).searchParams) if (!fora.has(k)) out[k] = v;
  return out;
}

test.beforeEach(async ({ page }) => {
  // Cada teste começa sem exportação herdada de outro (ela fica no localStorage).
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("e2e-limpo")) {
      for (const chave of Object.keys(localStorage)) {
        if (chave.startsWith("sgp.upfs.exportacao")) localStorage.removeItem(chave);
      }
      sessionStorage.setItem("e2e-limpo", "1");
    }
  });
});

// ─── 1. Backend real ─────────────────────────────────────────────────────────

test.describe("Exportação de UPFs — backend real (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("até 1.000 registros o CSV sai direto, com as colunas e o CPF completo", async ({ page }) => {
    const { download, count } = await exportarComListagem(page, "/sgp/upfs");

    // O nome vem do `Content-Disposition` do backend.
    expect(download.suggestedFilename()).toMatch(/^upfs_\d{4}-\d{2}-\d{2}.*\.csv$/);
    await expect(page.getByText(/Download de upfs_.*\.csv iniciado/)).toBeVisible();
    await expect(statusPanel(page)).toHaveCount(0);

    const { cabecalho, linhas } = await linhasDoCsv(download);
    expect(cabecalho).toBe(COLUNAS);
    expect(linhas).toHaveLength(count);
    // UGP vê o CPF completo (CPF_COMPLETO_ROLES).
    expect(linhas[0].split(",")[5]).toMatch(/^\d{11}$/);
  });

  test("o arquivo traz exatamente o conjunto filtrado, com os parâmetros da listagem", async ({
    page,
  }) => {
    const { download, count, urlListagem, urlExport } = await exportarComListagem(
      page,
      "/sgp/upfs?status=inativas",
    );

    expect(filtrosDe(urlExport)).toEqual(filtrosDe(urlListagem));
    expect(filtrosDe(urlExport)).toEqual({ ativo: "false" });
    expect(new URL(urlExport).searchParams.get("formato")).toBe("csv");

    const { linhas } = await linhasDoCsv(download);
    expect(count).toBeGreaterThan(0);
    expect(linhas).toHaveLength(count);
  });

  test("filtro com valor inválido: a API recusa e a tela mostra a mensagem dela", async ({
    page,
  }) => {
    await page.goto("/sgp/upfs?de=data-invalida");
    await botaoExportar(page).click();
    await expect(page.getByText("Informe uma data válida.").last()).toBeVisible();
    await expect(statusPanel(page)).toHaveCount(0);
  });
});

test.describe("Exportação de UPFs — backend real (escopo territorial)", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("Articulador exporta só o seu território, com o CPF mascarado", async ({ page }) => {
    const { download, count } = await exportarComListagem(page, "/sgp/upfs");
    const { linhas } = await linhasDoCsv(download);

    expect(linhas).toHaveLength(count);
    const estados = new Set(linhas.map((l) => l.split(",")[0]));
    for (const uf of estados) expect(["PE", "AL", "MA"]).toContain(uf);
    for (const l of linhas) expect(l.split(",")[5]).toMatch(/^\d{3}\.\*{3}\.\*{3}-\d{2}$/);
  });
});

// ─── 2. Exportação em segundo plano ─────────────────────────────────────────

test.describe("Exportação de UPFs — acima do limite, em segundo plano (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  let marco: number;

  test.beforeAll(() => {
    marco = marcoDosJobs();
    criarUpfsEmVolume();
  });

  test.afterAll(() => {
    removerUpfsEmVolume();
    apagarJobsDesde(marco);
  });

  /** Exporta e devolve o `count` da listagem que a tela mostrava. */
  async function exportar(page: Page): Promise<number> {
    const listagem = page.waitForResponse(
      (r) => /\/api\/v1\/upfs\/\?/.test(r.url()) && r.request().method() === "GET",
    );
    await page.goto("/sgp/upfs");
    const { count } = (await (await listagem).json()) as { count: number };
    const inicio = page.waitForResponse((r) => r.url().includes("/api/v1/upfs/exportar/"));
    await botaoExportar(page).click();
    expect((await inicio).status()).toBe(202);
    return count;
  }

  async function baixar(page: Page): Promise<Download> {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Baixar arquivo" }).click(),
    ]);
    return download;
  }

  test("vira exportação em segundo plano: aviso, andamento, conclusão e download", async ({ page }) => {
    const total = await exportar(page);
    expect(total).toBeGreaterThan(1000);

    await expect(page.getByText(`${total.toLocaleString("pt-BR")} registros`, { exact: false })).toBeVisible();
    await expect(statusPanel(page)).toHaveAttribute("data-status", /pendente|processando/);
    await expect(botaoExportar(page)).toBeDisabled();

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    await expect(botaoExportar(page)).toBeEnabled();

    const download = await baixar(page);
    expect(download.suggestedFilename()).toMatch(/^upfs_.*\.csv$/);
    const { cabecalho, linhas } = await linhasDoCsv(download);
    expect(cabecalho).toBe(COLUNAS);
    expect(linhas).toHaveLength(total);
  });

  test("a tela continua utilizável durante a geração", async ({ page }) => {
    await exportar(page);
    await expect(statusPanel(page)).toBeVisible();

    const novaListagem = page.waitForRequest(
      (req) => /\/api\/v1\/upfs\/\?/.test(req.url()) && req.url().includes("q=Jos"),
    );
    await page.getByPlaceholder("Buscar por nome ou CPF...").fill("Jos");
    await novaListagem;
    await expect(statusPanel(page)).toBeVisible();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
  });

  test("download posterior: a exportação sobrevive a sair e voltar", async ({ page }) => {
    await exportar(page);
    await page.goto("/sgp");
    await page.goto("/sgp/upfs");

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    expect((await baixar(page)).suggestedFilename()).toMatch(/^upfs_.*\.csv$/);
  });

  test("erro: mostra a mensagem do job e 'Tentar novamente' reenfileira pelo /repetir/", async ({ page }) => {
    const id = criarJob(UGP, "upfs", "erro");
    const origem = await abrirComApi(page, "/sgp/upfs");
    await guardarTarefaDeExportacao(page, origem, CHAVE_TAREFA, id);
    await page.reload();

    await expect(statusPanel(page)).toHaveAttribute("data-status", "erro");
    await expect(statusPanel(page)).toContainText("O worker não conseguiu gerar o arquivo.");

    const repetir = page.waitForResponse((r) => r.url().endsWith(`/api/v1/sgp/exportacoes/${id}/repetir/`));
    await page.getByRole("button", { name: "Tentar novamente" }).click();
    expect((await repetir).status()).toBe(202);

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 30_000 });
    expect((await baixar(page)).suggestedFilename()).toMatch(/^upfs_.*\.csv$/);
  });

  test("job que o backend não conhece mais (404): gerar de novo com os mesmos filtros", async ({ page }) => {
    const id = criarJob(UGP, "upfs", "pendente");
    const origem = await abrirComApi(page, "/sgp/upfs");
    // Filtro com poucas UPFs: a nova exportação sai na hora, como arquivo.
    const filtros = { search: "E2E-240 Titular 000" };
    await guardarTarefaDeExportacao(page, origem, CHAVE_TAREFA, id, filtros);
    await page.reload();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "pendente");

    apagarJob(id);
    await expect(statusPanel(page)).toHaveAttribute("data-status", "erro", { timeout: 10_000 });
    await expect(statusPanel(page)).toContainText("não está mais disponível");

    const pedido = page.waitForRequest((r) => r.url().includes("/api/v1/upfs/exportar/"));
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Tentar novamente" }).click(),
    ]);
    expect(new URL((await pedido).url()).searchParams.get("q")).toBe(filtros.search);
    const { linhas } = await linhasDoCsv(download);
    expect(linhas).toHaveLength(9);
  });

  test("arquivo expirado (410): avisa e oferece gerar novamente", async ({ page }) => {
    const id = criarJob(UGP, "upfs", "expirado");
    const origem = await abrirComApi(page, "/sgp/upfs");
    await guardarTarefaDeExportacao(page, origem, CHAVE_TAREFA, id);
    await page.reload();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida");

    const download = page.waitForResponse((r) => r.url().endsWith(`/api/v1/sgp/exportacoes/${id}/download/`));
    await page.getByRole("button", { name: "Baixar arquivo" }).click();
    expect((await download).status()).toBe(410);
    await expect(page.getByText("O arquivo desta exportação expirou.", { exact: false }).first()).toBeVisible();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "expirada");
    await expect(page.getByRole("button", { name: "Gerar novamente" })).toBeVisible();
  });

  test("erro inesperado do servidor mostra a mensagem genérica", async ({ page }) => {
    // Falha forçada: o único caso em que a resposta é interceptada.
    await page.route(
      (url) => url.pathname.startsWith("/api/v1/upfs/exportar/"),
      (route) =>
        route.request().method() === "OPTIONS"
          ? route.fallback()
          : route.fulfill({
              status: 500,
              headers: { "access-control-allow-origin": "*" },
              body: "Internal Server Error",
            }),
    );
    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(page.getByText(/Erro inesperado \(500\)|Não foi possível exportar/)).toBeVisible();
  });
});
