import { expect, test } from "@playwright/test";
import {
  criarMapaFixture,
  PREFIXO_MAPA,
  removerMapaFixture,
  TOTAL_UPFS_MAPA,
  type MapaFixture,
} from "./helpers/mapaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Mapa de UPFs (B6 da #302) contra o backend real. As UPFs próximas do
 * clustering vêm da fixture (`mapaFixture.ts`); só a falha 500 é forçada.
 */

const MAPA_API = "**/api/v1/upfs/mapa/**";

let fx: MapaFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarMapaFixture();
});

test.afterAll(() => {
  removerMapaFixture();
});

test.describe("SGP — Mapa de UPFs", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("página do mapa carrega e exibe o componente de mapa", async ({ page }) => {
    await page.goto("/sgp/upfs/mapa");
    await expect(page.getByRole("heading", { name: "UPFs" })).toBeVisible();
    await expect(page.locator(".leaflet-container")).toBeVisible();
    await expect(page.locator(".leaflet-marker-icon").first()).toBeVisible();
  });

  test("estado de erro exibe mensagem e botão Tentar novamente", async ({ page }) => {
    // Falha forçada: o único caso em que a resposta é interceptada.
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 500,
        headers: { "access-control-allow-origin": "*" },
        body: "Internal Server Error",
      });
    });

    await page.goto("/sgp/upfs/mapa");
    await expect(page.getByText(/Erro inesperado \(500\)|Não foi possível carregar/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  });

  test("estado vazio: município sem UPF com coordenadas", async ({ page }) => {
    await page.goto(`/sgp/upfs/mapa?municipio=${fx.municipioVazio}`);
    await expect(page.getByText(/Nenhuma UPF/i).first()).toBeVisible();
  });

  // Pendência de backend #377 (pendencias-backend-sprint-11.md, item 4): a chave do
  // cache do `/upfs/mapa/` não inclui o `q`, então por 60 s a busca devolve o
  // resultado sem filtro. Sai do `fixme` quando a chave incluir a busca.
  test.fixme("busca por texto sem resultado mostra o estado vazio", async ({ page }) => {
    await page.goto("/sgp/upfs/mapa");
    await expect(page.locator(".leaflet-marker-icon").first()).toBeVisible();
    await page.goto(`/sgp/upfs/mapa?q=${PREFIXO_MAPA}-nao-existe`);
    await expect(page.getByText(/Nenhuma UPF/i).first()).toBeVisible();
  });

  test("botão de filtros abre o painel lateral", async ({ page }) => {
    await page.goto("/sgp/upfs/mapa");
    const filterBtn = page.getByRole("button", { name: /Filtros/i });
    await expect(filterBtn).toBeVisible();
    await filterBtn.click();
    await expect(page.getByRole("dialog", { name: "Filtros" })).toBeVisible();
  });

  test("a visão de lista fica a um clique do mapa", async ({ page }) => {
    await page.goto("/sgp/upfs/mapa");
    const listBtn = page.getByRole("link", { name: /Lista/i }).or(page.getByRole("button", { name: /Lista/i }));
    await expect(listBtn.first()).toBeVisible();
  });

  test("UPFs próximas viram cluster; o clique expande e a UPF abre a mini-ficha", async ({ page }) => {
    await page.goto(`/sgp/upfs/mapa?municipio=${fx.municipio}`);
    await expect(page.locator(".leaflet-container")).toBeVisible();

    // O ícone de cluster usa <span class="mapview-cluster"> (markerIcons.ts).
    const cluster = page.locator(".mapview-cluster").first();
    await expect(cluster).toBeVisible();
    await expect(page.locator(".mapview-marker")).toHaveCount(0);
    // Os clusters somam todas as UPFs da fixture. Durante a animação inicial os
    // ícones antigos e os novos coexistem, por isso a soma é lida até assentar.
    await expect
      .poll(async () =>
        (await page.locator(".mapview-cluster").allTextContents()).reduce((soma, t) => soma + Number(t.trim()), 0),
      )
      .toBe(TOTAL_UPFS_MAPA);

    // O clique dá zoom-in e parte dos marcadores sai do cluster como ícones
    // individuais; o sinal da expansão é o aparecimento de .mapview-marker.
    // Coordenadas a ~1 m umas das outras podem pedir mais de um nível de zoom.
    await expect(async () => {
      await page.locator(".mapview-cluster").first().click();
      await expect(page.locator(".mapview-marker").first()).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 20_000 });

    await page.locator(".mapview-marker").first().click();
    const miniFicha = page.getByRole("dialog");
    await expect(miniFicha).toBeVisible();
    await expect(miniFicha).toContainText(PREFIXO_MAPA);
  });
});
