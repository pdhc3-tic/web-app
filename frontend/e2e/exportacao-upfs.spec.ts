import { expect, test, type Page, type Route } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #240 — Exportação da listagem de UPFs.
 *
 * O endpoint `/api/v1/upfs/exportar/` ainda não existe no backend, então as
 * respostas dele são forjadas aqui seguindo o contrato documentado em
 * `app/lib/upfs.ts` (200 = arquivo direto, 202 = tarefa, polling em
 * `exportar/{id}/`, arquivo em `exportar/{id}/arquivo/`). A LISTAGEM continua
 * vindo do backend real — é contra ela que a igualdade dos filtros é provada.
 *
 * O que estes testes NÃO cobrem, por ser responsabilidade do servidor: o
 * conteúdo das colunas, a máscara do CPF por perfil e o recorte territorial
 * dentro do arquivo (`apps/sgp/tests/test_upf_export.py`, a cargo do back).
 */

const PATH_INICIO = /\/api\/v1\/upfs\/exportar\/$/;
const PATH_TAREFA = /\/api\/v1\/upfs\/exportar\/([^/]+)\/$/;
const PATH_ARQUIVO = /\/api\/v1\/upfs\/exportar\/([^/]+)\/arquivo\/$/;

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-expose-headers": "content-disposition",
};

/** Parâmetros que só a paginação/ordenação da listagem usa — fora da comparação. */
const SO_DA_LISTAGEM = new Set(["limit", "offset", "ordering"]);

type Handlers = {
  inicio?: (route: Route, url: URL) => Promise<void>;
  tarefa?: (route: Route, id: string) => Promise<void>;
  arquivo?: (route: Route, id: string) => Promise<void>;
};

/** Roteia as três rotas da exportação; o preflight de CORS é respondido aqui. */
async function mockExportacao(page: Page, handlers: Handlers) {
  await page.route(
    (url) => url.pathname.startsWith("/api/v1/upfs/exportar/"),
    async (route) => {
      if (route.request().method() === "OPTIONS") {
        await route.fulfill({
          status: 204,
          headers: {
            ...CORS,
            "access-control-allow-methods": "GET, OPTIONS",
            "access-control-allow-headers": "authorization, content-type",
          },
        });
        return;
      }
      const url = new URL(route.request().url());
      const arquivo = PATH_ARQUIVO.exec(url.pathname);
      if (arquivo && handlers.arquivo) return handlers.arquivo(route, arquivo[1]);
      const tarefa = PATH_TAREFA.exec(url.pathname);
      if (!arquivo && tarefa && handlers.tarefa) return handlers.tarefa(route, tarefa[1]);
      if (PATH_INICIO.test(url.pathname) && handlers.inicio) return handlers.inicio(route, url);
      await route.fulfill({ status: 404, headers: CORS, body: "{}" });
    },
  );
}

function csv(route: Route, nome: string) {
  return route.fulfill({
    status: 200,
    headers: {
      ...CORS,
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="${nome}"`,
    },
    body: "estado,municipio,territorio,comunidade,titular,cpf,cadastrado_em\r\n",
  });
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    headers: { ...CORS, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function tarefa(status: string, extra: Record<string, unknown> = {}) {
  return {
    id: "exp-1",
    status,
    total: 1500,
    progresso: null,
    erro: null,
    arquivo_nome: "upfs_2026-09-23.csv",
    ...extra,
  };
}

function filtrosDe(url: string): Record<string, string> {
  const params = new URL(url).searchParams;
  const out: Record<string, string> = {};
  for (const [k, v] of params) if (!SO_DA_LISTAGEM.has(k) && k !== "formato") out[k] = v;
  return out;
}

const statusPanel = (page: Page) => page.getByTestId("upfs-exportacao-status");
const botaoExportar = (page: Page) => page.getByRole("button", { name: "Exportar" });

test.describe("SGP — Exportação da listagem de UPFs", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.beforeEach(async ({ page }) => {
    // Cada teste começa sem tarefa de exportação herdada de outro.
    await page.addInitScript(() => {
      if (!sessionStorage.getItem("e2e-limpo")) {
        localStorage.removeItem("sgp.upfs.exportacao");
        sessionStorage.setItem("e2e-limpo", "1");
      }
    });
  });

  test("até 1.000 registros o download sai direto, sem tarefa em segundo plano", async ({
    page,
  }) => {
    await mockExportacao(page, {
      inicio: (route) => csv(route, "upfs_2026-09-23.csv"),
    });

    await page.goto("/sgp/upfs");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      botaoExportar(page).click(),
    ]);

    expect(download.suggestedFilename()).toBe("upfs_2026-09-23.csv");
    await expect(page.getByText(/Download de upfs_2026-09-23\.csv iniciado/)).toBeVisible();
    await expect(statusPanel(page)).toHaveCount(0);
  });

  test("exatamente 1.000 registros ainda é download direto", async ({ page }) => {
    // O limite é aplicado no servidor: com 1.000 ele responde 200 com o arquivo,
    // e a tela não pode tratar isso como tarefa.
    await mockExportacao(page, {
      inicio: (route) => csv(route, "upfs_1000.csv"),
    });

    await page.goto("/sgp/upfs");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      botaoExportar(page).click(),
    ]);

    expect(download.suggestedFilename()).toBe("upfs_1000.csv");
    await expect(statusPanel(page)).toHaveCount(0);
  });

  test("o arquivo usa exatamente os filtros da listagem", async ({ page }) => {
    let urlExport: string | null = null;
    await mockExportacao(page, {
      inicio: async (route, url) => {
        urlExport = url.toString();
        await csv(route, "upfs.csv");
      },
    });

    // Espera a listagem JÁ filtrada: a primeira requisição do mount serve de base.
    const listagem = page.waitForRequest(
      (req) =>
        /\/api\/v1\/upfs\/\?/.test(req.url()) && req.url().includes("cadastrado_ate="),
    );
    await page.goto(
      "/sgp/upfs?q=Maria&municipio=1001&status=inativas&de=2026-01-01&ate=2026-06-30",
    );
    const urlListagem = (await listagem).url();

    await Promise.all([page.waitForEvent("download"), botaoExportar(page).click()]);

    expect(urlExport).not.toBeNull();
    const esperado = {
      q: "Maria",
      municipio: "1001",
      ativo: "false",
      cadastrado_de: "2026-01-01",
      cadastrado_ate: "2026-06-30",
    };
    expect(filtrosDe(urlListagem)).toEqual(esperado);
    expect(filtrosDe(urlExport!)).toEqual(esperado);
    expect(new URL(urlExport!).searchParams.get("formato")).toBe("csv");
  });

  test("acima de 1.000 registros vira tarefa: aviso, progresso, conclusão e download", async ({
    page,
  }) => {
    let consultas = 0;
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, tarefa("pendente")),
      tarefa: (route) => {
        consultas += 1;
        return json(
          route,
          200,
          consultas === 1
            ? tarefa("processando", { progresso: 40 })
            : tarefa("concluida", { progresso: 100 }),
        );
      },
      arquivo: (route) => csv(route, "upfs_2026-09-23.csv"),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();

    await expect(page.getByText(/1\.500 registros.*segundo plano/)).toBeVisible();
    await expect(statusPanel(page)).toBeVisible();
    // Uma exportação por vez: o botão fica bloqueado enquanto a tarefa roda.
    await expect(botaoExportar(page)).toBeDisabled();

    await expect(statusPanel(page)).toHaveAttribute("data-status", "processando");
    await expect(statusPanel(page)).toContainText("40%");

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", {
      timeout: 10_000,
    });
    await expect(page.getByText(/Exportação concluída/).first()).toBeVisible();
    await expect(botaoExportar(page)).toBeEnabled();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Baixar arquivo" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("upfs_2026-09-23.csv");
  });

  test("a tela continua utilizável durante a geração", async ({ page }) => {
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, tarefa("pendente")),
      tarefa: (route) => json(route, 200, tarefa("processando", { progresso: 10 })),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "processando");

    // Filtrar dispara uma nova listagem normalmente, com o painel ainda na tela.
    const novaListagem = page.waitForRequest(
      (req) => /\/api\/v1\/upfs\/\?/.test(req.url()) && req.url().includes("q=Jos"),
    );
    await page.getByPlaceholder("Buscar por nome ou CPF...").fill("Jos");
    await novaListagem;
    await expect(statusPanel(page)).toBeVisible();
  });

  test("download posterior: a tarefa sobrevive a um reload e o arquivo fica disponível", async ({
    page,
  }) => {
    let concluida = false;
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, tarefa("pendente")),
      tarefa: (route) =>
        json(route, 200, concluida ? tarefa("concluida") : tarefa("processando", { progresso: 20 })),
      arquivo: (route) => csv(route, "upfs_2026-09-23.csv"),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();
    await expect(statusPanel(page)).toHaveAttribute("data-status", "processando");

    // Sai e volta: o acompanhamento é retomado a partir do que ficou gravado.
    await page.goto("/sgp");
    concluida = true;
    await page.goto("/sgp/upfs");

    await expect(statusPanel(page)).toHaveAttribute("data-status", "concluida", {
      timeout: 10_000,
    });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Baixar arquivo" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("upfs_2026-09-23.csv");
  });

  test("falha da tarefa mostra a mensagem e 'Tentar novamente' repete com os mesmos filtros", async ({
    page,
  }) => {
    const pedidos: string[] = [];
    await mockExportacao(page, {
      inicio: (route, url) => {
        pedidos.push(url.search);
        return pedidos.length === 1
          ? json(route, 202, tarefa("pendente"))
          : csv(route, "upfs_2026-09-23.csv");
      },
      tarefa: (route) =>
        json(route, 200, tarefa("falhou", { erro: "O worker de exportação ficou indisponível." })),
    });

    await page.goto("/sgp/upfs?municipio=1001");
    await botaoExportar(page).click();

    await expect(statusPanel(page)).toHaveAttribute("data-status", "falhou", {
      timeout: 10_000,
    });
    await expect(statusPanel(page)).toContainText("O worker de exportação ficou indisponível.");

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Tentar novamente" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("upfs_2026-09-23.csv");
    expect(pedidos).toHaveLength(2);
    expect(pedidos[1]).toBe(pedidos[0]);
    await expect(statusPanel(page)).toHaveCount(0);
  });

  test("tarefa que o backend não conhece mais (404) vira falha com opção de gerar de novo", async ({
    page,
  }) => {
    await mockExportacao(page, {
      inicio: (route) => json(route, 202, tarefa("pendente")),
      tarefa: (route) => json(route, 404, { detail: "Não encontrado." }),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();

    await expect(statusPanel(page)).toHaveAttribute("data-status", "falhou", {
      timeout: 10_000,
    });
    await expect(statusPanel(page)).toContainText("não está mais disponível");
    await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  });

  test("parâmetro recusado pela API mostra a mensagem do backend", async ({ page }) => {
    await mockExportacao(page, {
      inicio: (route) =>
        json(route, 400, {
          code: "validation_error",
          message: "Parâmetro de filtro desconhecido: bairro.",
        }),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();

    await expect(page.getByText("Parâmetro de filtro desconhecido: bairro.")).toBeVisible();
    await expect(statusPanel(page)).toHaveCount(0);
  });

  test("erro inesperado mostra a mensagem genérica", async ({ page }) => {
    await mockExportacao(page, {
      inicio: (route) =>
        route.fulfill({ status: 500, headers: CORS, body: "Internal Server Error" }),
    });

    await page.goto("/sgp/upfs");
    await botaoExportar(page).click();

    await expect(page.getByText(/Erro inesperado \(500\)|Não foi possível exportar/)).toBeVisible();
  });
});

test.describe("SGP — Exportação de UPFs por perfil com escopo territorial", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("perfil com escopo territorial também exporta a sua listagem", async ({ page }) => {
    let pedido = false;
    await mockExportacao(page, {
      inicio: async (route) => {
        pedido = true;
        await csv(route, "upfs.csv");
      },
    });

    await page.goto("/sgp/upfs");
    await expect(botaoExportar(page)).toBeVisible();
    await Promise.all([page.waitForEvent("download"), botaoExportar(page).click()]);
    expect(pedido).toBe(true);
  });
});
