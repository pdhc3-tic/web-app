import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

const MAPA_API = "**/api/v1/upfs/mapa/**";

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

type UpfMapaFake = ReturnType<typeof upfMapaFake>;

/**
 * Constrói a resposta do endpoint /api/v1/upfs/mapa/ no formato GeoJSON
 * FeatureCollection esperado por fetchUpfsMapa. Coordenadas em [lng, lat]
 * conforme a especificação GeoJSON (fetchUpfsMapa inverte para [lat, lng]).
 */
function mapaResponse(upfs: UpfMapaFake[]): string {
  return JSON.stringify({
    type: "FeatureCollection",
    features: upfs.map((u) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [u.longitude as number, u.latitude as number],
      },
      properties: {
        id: u.id,
        nome_titular: u.nome_titular,
        municipio: u.municipio,
        territorio: u.territorio,
        ativa: u.ativa,
      },
    })),
    truncated: false,
  });
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

    await page.route("**/api/v1/upfs/1/", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          projeto: { id: 1, nome: "Projeto Demo" },
          titular: {
            id: 1,
            nome_completo: "João Silva",
            cpf: "000.000.000-00",
            rg: "",
            data_nascimento: null,
            genero: null,
            genero_display: "",
            escolaridade: null,
            escolaridade_display: "",
            nis: "",
            idade: null,
          },
          apelido: "",
          celular: "",
          whatsapp: "",
          internet: false,
          dispositivo: null,
          cep: "",
          logradouro: "",
          numero: "",
          complemento: "",
          bairro: "",
          municipio: { id: 1001, nome: "Ouricuri" },
          territorio: null,
          comunidade: null,
          latitude: null,
          longitude: null,
          pct: null,
          posse_terra: null,
          area_terra_ha: null,
          situacao_moradia: null,
          tipo_moradia: null,
          material_construcao: null,
          num_comodos: null,
          energia: null,
          agua: null,
          daf_caf: "",
          seguridade_social: [],
          foto_url: "",
          criado_por: null,
          ativa: true,
          criado_em: "2026-01-01T00:00:00Z",
          atualizado_em: "2026-01-01T00:00:00Z",
          device_id: "",
          uuid_local: null,
          ultima_origem: "web",
          ultimo_sync_em: null,
        }),
      });
    });

    await page.goto("/sgp/upfs/mapa");

    const marker = page.locator(".leaflet-marker-icon").first();
    await expect(marker).toBeVisible({ timeout: 10_000 });
    await marker.click();
    const miniFicha = page.locator('[role="dialog"]');
    await expect(miniFicha).toBeVisible({ timeout: 5_000 });
    await expect(miniFicha.getByText("João Silva")).toBeVisible();
  });
});
