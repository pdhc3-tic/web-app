import fs from "node:fs";
import { expect, test } from "@playwright/test";
import {
  criarPainelFiltrosFixture,
  removerPainelFiltrosFixture,
  statusDaDemanda,
  type PainelFiltrosFixture,
} from "./helpers/painelFiltrosFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #456 — Painel de Demandas com filtros, exportação, paginação, coluna
 * Atividade, Nova demanda e o cancelamento pelo próprio solicitante. Contra o
 * backend real.
 */

let fx: PainelFiltrosFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarPainelFiltrosFixture();
});

test.afterAll(() => {
  removerPainelFiltrosFixture();
});

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("filtra por status, exporta o recorte e a fila não usa os filtros", async ({ page }) => {
    await page.goto("/sgd/demandas");
    // A UGP não cria demanda; na fila, não há filtros nem exportação.
    await expect(page.getByTestId("demandas-visao-minha")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("demandas-nova-btn")).toHaveCount(0);
    await expect(page.getByTestId("demandas-filtros")).toHaveCount(0);

    await page.getByTestId("demandas-visao-todas").click();
    const filtros = page.getByTestId("demandas-filtros");
    await expect(filtros).toBeVisible();

    await filtros.getByRole("combobox", { name: "Status" }).click();
    await page.getByRole("option", { name: "Rascunho", exact: true }).click();
    await expect(page).toHaveURL(/status=rascunho/);

    const tabela = page.getByTestId("demandas-tabela");
    const linha = page.getByTestId(`demanda-linha-${fx.filtrada.id}`);
    await expect(linha).toBeVisible();
    // Só Rascunhos na lista.
    await expect(tabela.locator("tbody tr").filter({ hasNotText: "Rascunho" })).toHaveCount(0);
    // A paginação aparece mesmo com uma página só.
    await expect(page.getByText(/de \d+ demandas?/)).toBeVisible();

    // A coluna Atividade leva à ficha da atividade.
    await expect(page.getByTestId(`demanda-atividade-${fx.filtrada.id}`)).toHaveAttribute(
      "href",
      `/sgp/atividades/${fx.atividadeId}`,
    );

    // A exportação leva o filtro.
    const pedido = page.waitForRequest(/\/api\/v1\/sgd\/demandas\/exportar\//);
    const download = page.waitForEvent("download");
    await page.getByTestId("exportar-csv-btn").click();
    const url = new URL((await pedido).url());
    expect(url.searchParams.get("formato")).toBe("csv");
    expect(url.searchParams.get("status")).toBe("rascunho");
    const arquivo = await download;
    const conteudo = fs.readFileSync((await arquivo.path())!, "utf8");
    expect(conteudo).toContain(fx.filtrada.titulo);

    // A faixa "Voltar ao painel" é do drill-down da Execução, não de um filtro daqui.
    await expect(page.getByTestId("filtro-atividade-ativo")).toHaveCount(0);

    // Voltar à fila limpa os filtros.
    await page.getByTestId("demandas-visao-minha").click();
    await expect(page).not.toHaveURL(/status=/);
    await expect(page.getByTestId("demandas-filtros")).toHaveCount(0);
  });
});

test.describe("ADT (solicitante)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("tem Nova demanda e cancela o próprio rascunho, sem justificativa", async ({ page }) => {
    await page.goto("/sgd/demandas");
    await expect(page.getByTestId("demandas-filtros")).toBeVisible();
    await expect(page.getByTestId("demandas-nova-btn")).toHaveAttribute("href", "/sgd/demandas/nova");

    await page.getByTestId(`demanda-linha-${fx.aCancelar.id}`).getByRole("button").click();
    const painel = page.getByTestId("demanda-painel");
    await painel.getByTestId("acao-cancelar-solicitante").click();
    const drawer = page.getByTestId("cancelar-solicitante-drawer");
    await expect(drawer).toContainText("será encerrada e não poderá ser reaberta");
    await page.getByTestId("cancelar-solicitante-drawer-confirmar").click();

    await expect(painel).toContainText("Demanda cancelada.");
    await expect(painel.getByTestId("acao-cancelar-solicitante")).toHaveCount(0);
    await expect(page.getByTestId(`demanda-linha-${fx.aCancelar.id}`)).toContainText("Cancelada");
    expect(statusDaDemanda(fx.aCancelar.id)).toBe("cancelada");
  });
});
