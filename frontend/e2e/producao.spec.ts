import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

const PRODUCAO_API = "**/api/v1/sgp/producao/**";
const INDICADORES_API = "**/api/v1/sgp/producao/indicadores/**";

function producaoFake(
  id: number,
  upfId: number,
  nomeTitular: string,
  tipo: "agricola" | "pecuaria" | "outra",
  culturaNome?: string,
  municipio = "Ouricuri",
  territorio?: string,
): Record<string, unknown> {
  return {
    id,
    upf_id: upfId,
    upf_nome_titular: nomeTitular,
    tipo,
    cultura: culturaNome ? { id: 1, nome: culturaNome, categoria: "Grãos" } : null,
    especie: null,
    area_ha: tipo === "agricola" ? "2.5" : null,
    producao_estimada: null,
    unidade_producao: null,
    sementes_crioulas: false,
    n_matrizes: null,
    n_reprodutores: null,
    n_jovens: null,
    area_pastejo_ha: null,
    sistema_criacao: null,
    tipo_outra: null,
    descricao_outra: null,
    quantidade_produzida: null,
    renda_estimada_mensal: null,
    custo_anual: null,
    observacoes: null,
    municipio,
    territorio: territorio ?? null,
  };
}

function paginated(results: unknown[]): string {
  return JSON.stringify({ count: results.length, next: null, previous: null, results });
}

const indicadoresFake = {
  total_upfs_produtoras: 12,
  area_total_ha: "48.50",
  principais_culturas: [
    { nome: "Milho", count: 8 },
    { nome: "Feijão", count: 6 },
    { nome: "Mandioca", count: 4 },
  ],
};

test.describe("SGP — Produção da UPF consolidada", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("card Produção aparece na página do SGP com link funcional", async ({
    page,
  }) => {
    await page.goto("/sgp");
    const card = page.getByRole("link", { name: /Produção da UPF/i });
    await expect(card).toBeVisible();
    const href = await card.getAttribute("href");
    expect(href).toContain("/sgp/producao");
  });

  test("listagem exibe colunas e indicadores agregados", async ({ page }) => {
    await page.route(INDICADORES_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(indicadoresFake),
      });
    });

    await page.route(PRODUCAO_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          producaoFake(1, 10, "João Silva", "agricola", "Milho", "Ouricuri", "Sertão Central"),
          producaoFake(2, 11, "Maria Santos", "pecuaria", undefined, "Petrolina"),
        ]),
      });
    });

    await page.goto("/sgp/producao");

    await expect(page.getByText("UPFs produtoras")).toBeVisible();
    await expect(page.getByText("12")).toBeVisible();
    await expect(page.getByText("48,5")).toBeVisible();

    await expect(page.getByRole("columnheader", { name: "UPF / Titular" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Tipo" })).toBeVisible();

    await expect(page.getByText("João Silva")).toBeVisible();
    await expect(page.getByText("Agrícola")).toBeVisible();
    await expect(page.getByText("Maria Santos")).toBeVisible();
    await expect(page.getByText("Pecuária")).toBeVisible();
  });

  test("link do titular aponta para a aba Produção da ficha da UPF", async ({
    page,
  }) => {
    await page.route(INDICADORES_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ total_upfs_produtoras: 1, area_total_ha: null, principais_culturas: [] }),
      });
    });

    await page.route(PRODUCAO_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          producaoFake(1, 42, "João Silva", "agricola", "Milho"),
        ]),
      });
    });

    await page.goto("/sgp/producao");
    const link = page.getByRole("link", { name: "João Silva" });
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    expect(href).toBe("/sgp/upfs/42#producao");
  });

  test("estado vazio sem filtros exibe mensagem", async ({ page }) => {
    await page.route(INDICADORES_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ total_upfs_produtoras: 0, area_total_ha: null, principais_culturas: [] }),
      });
    });

    await page.route(PRODUCAO_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([]),
      });
    });

    await page.goto("/sgp/producao");
    await expect(page.getByText("Nenhuma produção cadastrada")).toBeVisible();
  });

  test("estado vazio com filtros exibe botão Limpar filtros", async ({ page }) => {
    await page.route(INDICADORES_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ total_upfs_produtoras: 0, area_total_ha: null, principais_culturas: [] }),
      });
    });

    await page.route(PRODUCAO_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([]),
      });
    });

    await page.goto("/sgp/producao?tipo=agricola");
    await expect(page.getByText("Nenhum registro encontrado")).toBeVisible();
    await expect(page.getByRole("button", { name: "Limpar filtros" })).toBeVisible();
  });

  test("erro na API exibe mensagem e botão Tentar novamente", async ({ page }) => {
    await page.route(INDICADORES_API, async (route) => {
      await route.fulfill({ status: 500, body: "error" });
    });

    await page.route(PRODUCAO_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({ status: 500, body: "error" });
    });

    await page.goto("/sgp/producao");
    await expect(page.getByText(/Não foi possível carregar/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  });
});
