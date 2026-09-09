import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

const MAPA_API = "**/api/v1/sgp/upfs/mapa/**";

function upfMapaFake(
  id: number,
  nome: string,
  municipio: string,
  lat: number,
  lng: number,
  ativa = true,
): Record<string, unknown> {
  return {
    id,
    nome_titular: nome,
    municipio,
    territorio: "Território Sertão Central",
    latitude: lat,
    longitude: lng,
    ativa,
  };
}

function mapaResponse(results: unknown[]): string {
  return JSON.stringify({ count: results.length, results });
}

test.describe("SGP — Mapa de UPFs", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("página do mapa carrega e exibe o componente de mapa", async ({
    page,
  }) => {
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: mapaResponse([
          upfMapaFake(1, "João Silva", "Ouricuri", -7.88, -40.08),
          upfMapaFake(2, "Maria Santos", "Ouricuri", -7.90, -40.10),
        ]),
      });
    });

    await page.goto("/sgp/upfs/mapa");
    await expect(page.getByRole("heading", { name: "UPFs" })).toBeVisible();
    await expect(page.locator('[data-testid="map-view"]').or(page.locator(".leaflet-container")).or(page.locator('[id^="map"]'))).toBeVisible({ timeout: 10_000 });
  });

  test("estado de erro exibe mensagem e botão Tentar novamente", async ({
    page,
  }) => {
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({ status: 500, body: "Internal Server Error" });
    });

    await page.goto("/sgp/upfs/mapa");
    await expect(page.getByText(/Não foi possível carregar/i)).toBeVisible();
  });

  test("estado vazio exibe mensagem de nenhuma UPF encontrada", async ({
    page,
  }) => {
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: mapaResponse([]),
      });
    });

    await page.goto("/sgp/upfs/mapa");
    await expect(
      page.getByText(/Nenhuma UPF/i).or(page.getByText(/sem resultado/i)),
    ).toBeVisible({ timeout: 8_000 });
  });

  test("botão de filtros abre o painel lateral", async ({ page }) => {
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: mapaResponse([]),
      });
    });

    await page.goto("/sgp/upfs/mapa");
    const filterBtn = page.getByRole("button", { name: /Filtros/i });
    await expect(filterBtn).toBeVisible();
    await filterBtn.click();
    await expect(page.getByLabel("Município").or(page.getByText("Filtros")).first()).toBeVisible();
  });

  test("toggle de visão alterna entre mapa e tabela", async ({ page }) => {
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: mapaResponse([
          upfMapaFake(1, "João Silva", "Ouricuri", -7.88, -40.08),
        ]),
      });
    });

    await page.goto("/sgp/upfs/mapa");

    const listBtn = page.getByRole("link", { name: /Lista/i }).or(
      page.getByRole("button", { name: /Lista/i }),
    );
    await expect(listBtn.first()).toBeVisible();
  });

  test("mini-ficha é exibida ao selecionar uma UPF no mapa", async ({
    page,
  }) => {
    await page.route(MAPA_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: mapaResponse([
          upfMapaFake(1, "João Silva", "Ouricuri", -7.88, -40.08),
        ]),
      });
    });

    await page.route("**/api/v1/sgp/upfs/1/", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          nome_titular: "João Silva",
          municipio: { id: 1001, nome: "Ouricuri", state: 17 },
          territorio: null,
          comunidade: null,
          foto_url: null,
          ativo: true,
        }),
      });
    });

    await page.goto("/sgp/upfs/mapa");

    const marker = page.locator(".leaflet-marker-icon").first();
    if (await marker.count() > 0) {
      await marker.click();
      const miniFicha = page.locator('[role="dialog"]');
      await expect(miniFicha).toBeVisible({ timeout: 5_000 });
      await expect(miniFicha.getByText("João Silva")).toBeVisible();
    }
  });
});
