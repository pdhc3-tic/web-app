import { readFile } from "node:fs/promises";
import { expect, test, type Download, type Page, type Route } from "@playwright/test";
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
 * 2. **Estados da exportação assíncrona, com respostas forjadas.** Acima de
 *    1.000 UPFs o backend responde 202 e o job é acompanhado em
 *    `/api/v1/sgp/exportacoes/{id}/`; o seed tem 41 UPFs e o limite está fixo
 *    no código (`UPF_EXPORT_SYNC_LIMIT`, docs/pendencias-backend-sprint-10.md,
 *    item 3), então esses estados só são alcançáveis forjando a resposta —
 *    sempre no formato do `ExportJobSerializer`.
 */

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
      localStorage.removeItem("sgp.upfs.exportacao");
      sessionStorage.setItem("e2e-limpo", "1");
    }
  });
});

// ─── 1. Backend real ─────────────────────────────────────────────────────────

test.describe("Exportação de UPFs — backend real (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("até 1.000 registros o CSV sai direto, com as colunas e o CPF completo", async ({ page }) => {
    const { download, count } = await exportarComListagem(page, "/sgp/upfs");

    // O nome vem do backend; sem CORS_EXPOSE_HEADERS o front deriva o mesmo
    // padrão (pendência 2).
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

// ─── 2. Estados assíncronos (resposta forjada) ───────────────────────────────

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-expose-headers": "content-disposition",
};

type Handlers = {
  inicio?: (route: Route, url: URL) => Promise<void>;
  job?: (route: Route) => Promise<void>;
  download?: (route: Route) => Promise<void>;
  repetir?: (route: Route) => Promise<void>;
};

/** Forja as rotas da exportação; o preflight de CORS é respondido aqui. */
async function mockExportacao(page: Page, h: Handlers) {
  await page.route(
    (url) =>
      url.pathname.startsWith("/api/v1/upfs/exportar/") ||
      url.pathname.startsWith("/api/v1/sgp/exportacoes/"),
    async (route) => {
      const req = route.request();
      if (req.method() === "OPTIONS") {
        await route.fulfill({
          status: 204,
          headers: {
            ...CORS,
            "access-control-allow-methods": "GET, POST, OPTIONS",
            "access-control-allow-headers": "authorization, content-type",
          },
        });
        return;
      }
      const url = new URL(req.url());
      if (url.pathname.startsWith("/api/v1/upfs/exportar/") && h.inicio) return h.inicio(route, url);
      if (url.pathname.endsWith("/download/") && h.download) return h.download(route);
      if (url.pathname.endsWith("/repetir/") && h.repetir) return h.repetir(route);
      if (/\/exportacoes\/\d+\/$/.test(url.pathname) && h.job) return h.job(route);
      await route.fulfill({ status: 404, headers: CORS, body: '{"detail":"Não encontrado."}' });
    },
  );
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    headers: { ...CORS, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function csv(route: Route, nome: string) {
  return route.fulfill({
    status: 200,
    headers: {
      ...CORS,
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="${nome}"`,
    },
    body: `${COLUNAS}\r\n`,
  });
}

/** Um `ExportJobSerializer` com 1.500 UPFs. */
function job(status: string, extra: Record<string, unknown> = {}) {
  return {
    id: 7,
    tipo: "upfs",
    formato: "csv",
    filtros: {},
    status,
    progresso: 0,
    erro: "",
    total_registros: 1500,
    nome_arquivo: "upfs_2026-10-01_10-00-00.csv",
    criado_em: "2026-10-01T10:00:00-03:00",
    concluido_em: null,
    expira_em: null,
    ...extra,
  };
}

test.describe("Exportação de UPFs — acima de 1.000 registros (job forjado)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("vira exportação em segundo plano: aviso, progresso, conclusão e download", async ({
    page,
  }) => {
    let consultas = 0;
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, job("pendente")),
      job: (route) => {
        consultas += 1;
        return json(
          route,
          200,
          consultas === 1 ? job("processando", { progresso: 40 }) : job("concluida", { progresso: 100 }),
        );
      },
      download: (route) => csv(route, "upfs_2026-10-01_10-00-00.csv"),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();

    await expect(page.getByText(/1\.500 registros.*segundo plano/)).toBeVisible();
    await expect(botaoExportar(page)).toBeDisabled();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "processando");
    await expect(statusPanel(page)).toContainText("40%");

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 10_000 });
    await expect(botaoExportar(page)).toBeEnabled();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Baixar arquivo" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("upfs_2026-10-01_10-00-00.csv");
  });

  test("a tela continua utilizável durante a geração", async ({ page }) => {
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, job("pendente")),
      job: (route) => json(route, 200, job("processando", { progresso: 10 })),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "processando");

    const novaListagem = page.waitForRequest(
      (req) => /\/api\/v1\/upfs\/\?/.test(req.url()) && req.url().includes("q=Jos"),
    );
    await page.getByPlaceholder("Buscar por nome ou CPF...").fill("Jos");
    await novaListagem;
    await expect(statusPanel(page)).toBeVisible();
  });

  test("download posterior: a exportação sobrevive a sair e voltar", async ({ page }) => {
    let concluida = false;
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, job("pendente")),
      job: (route) =>
        json(route, 200, concluida ? job("concluida", { progresso: 100 }) : job("processando", { progresso: 20 })),
      download: (route) => csv(route, "upfs_2026-10-01_10-00-00.csv"),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "processando");

    await page.goto("/sgp");
    concluida = true;
    await page.goto("/sgp/upfs");

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 10_000 });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Baixar arquivo" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("upfs_2026-10-01_10-00-00.csv");
  });

  test("erro: mostra a mensagem e 'Tentar novamente' reenfileira pelo /repetir/", async ({ page }) => {
    let repetida = false;
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, job("pendente")),
      job: (route) =>
        json(
          route,
          200,
          repetida
            ? job("concluida", { progresso: 100 })
            : job("erro", { erro: "O worker de exportação ficou indisponível." }),
        ),
      repetir: (route) => {
        repetida = true;
        return json(route, 202, job("pendente"));
      },
      download: (route) => csv(route, "upfs_2026-10-01_10-00-00.csv"),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();

    await expect(statusPanel(page)).toHaveAttribute("data-status", "erro", { timeout: 10_000 });
    await expect(statusPanel(page)).toContainText("O worker de exportação ficou indisponível.");

    const pedidoRepetir = page.waitForRequest(
      (r) => r.url().endsWith("/api/v1/sgp/exportacoes/7/repetir/") && r.method() === "POST",
    );
    await page.getByRole("button", { name: "Tentar novamente" }).click();
    await pedidoRepetir;

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 10_000 });
  });

  test("exportação que o backend não conhece mais (404): gerar de novo com os mesmos filtros", async ({
    page,
  }) => {
    const pedidos: string[] = [];
    await mockExportacao(page, {
      inicio: (route, url) => {
        pedidos.push(url.search);
        return pedidos.length === 1 ? json(route, 202, job("pendente")) : csv(route, "upfs.csv");
      },
      job: (route) => json(route, 404, { detail: "Não encontrado." }),
    });

    await page.goto("/sgp/upfs?status=todas");
    await botaoExportar(page).click();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "erro", { timeout: 10_000 });
    await expect(statusPanel(page)).toContainText("não está mais disponível");

    await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Tentar novamente" }).click(),
    ]);
    expect(pedidos).toHaveLength(2);
    expect(pedidos[1]).toBe(pedidos[0]);
  });

  test("arquivo expirado (410): avisa e oferece gerar novamente", async ({ page }) => {
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, job("pendente")),
      job: (route) => json(route, 200, job("concluida", { progresso: 100 })),
      download: (route) =>
        json(route, 410, {
          code: "exportacao_expirada",
          message: "O arquivo desta exportação expirou. Gere uma nova exportação.",
        }),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", { timeout: 10_000 });

    await page.getByRole("button", { name: "Baixar arquivo" }).click();
    await expect(page.getByText("O arquivo desta exportação expirou.", { exact: false }).first()).toBeVisible();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "expirada");
    await expect(page.getByRole("button", { name: "Gerar novamente" })).toBeVisible();
  });

  test("erro inesperado do servidor mostra a mensagem genérica", async ({ page }) => {
    await mockExportacao(page, {
      inicio: (route) => route.fulfill({ status: 500, headers: CORS, body: "Internal Server Error" }),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(page.getByText(/Erro inesperado \(500\)|Não foi possível exportar/)).toBeVisible();
  });
});
