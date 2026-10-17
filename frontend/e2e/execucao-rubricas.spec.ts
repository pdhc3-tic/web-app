import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

const PAINEL_API = "**/api/v1/sgd/painel/rubricas/**";
const CUSTO_API = "**/api/v1/sgd/relatorios/custo-por-atividade/**";
const EXPORTAR_API = "**/api/v1/sgd/demandas/exportar/**";
const TERRITORIOS_API = "**/api/v1/territorios/**";

const FAKE_TERRITORIOS = [
  { id: 12, nome: "Sertão do São Francisco" },
  { id: 15, nome: "Agreste Central" },
];

test.describe("SGD — Painel de Execução por Rubrica e Custos (Issue #297)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.beforeEach(async ({ page }) => {
    await page.route(TERRITORIOS_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_TERRITORIOS),
      });
    });
  });

  test("painel por rubrica exibe os valores corretos para uma rubrica com movimentação conhecida", async ({
    page,
  }) => {
    await page.route(PAINEL_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            rubrica_id: 1,
            rubrica_slug: "diarias",
            rubrica_nome: "Diárias",
            solicitado: "1400.00",
            autorizado: "800.00",
            executado: "500.00",
            disponivel: "8500.00",
          },
        ]),
      });
    });

    await page.goto("/sgd/execucao");

    const tabela = page.getByTestId("tabela-painel-rubricas");
    await expect(tabela).toBeVisible();

    const linhaDiarias = page.getByTestId("rubrica-linha-diarias");
    await expect(linhaDiarias).toBeVisible();
    await expect(linhaDiarias.getByText("Diárias")).toBeVisible();
    await expect(linhaDiarias.getByText("R$ 1.400,00")).toBeVisible();
    await expect(linhaDiarias.getByText("R$ 800,00")).toBeVisible();
    await expect(linhaDiarias.getByText("R$ 500,00")).toBeVisible();
    await expect(linhaDiarias.getByText("R$ 8.500,00")).toBeVisible();
  });

  test("rubrica com execução acima de 90% exibe o semáforo vermelho; entre 70% e 90%, o amarelo", async ({
    page,
  }) => {
    await page.route(PAINEL_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            rubrica_id: 1,
            rubrica_slug: "passagens",
            rubrica_nome: "Passagens",
            solicitado: "1000.00",
            autorizado: "1000.00",
            executado: "950.00",
            disponivel: "50.00", // 95% -> Vermelho
          },
          {
            rubrica_id: 2,
            rubrica_slug: "diarias",
            rubrica_nome: "Diárias",
            solicitado: "1000.00",
            autorizado: "800.00",
            executado: "750.00",
            disponivel: "250.00", // 75% -> Amarelo (Terracota)
          },
          {
            rubrica_id: 3,
            rubrica_slug: "combustivel",
            rubrica_nome: "Combustível",
            solicitado: "500.00",
            autorizado: "300.00",
            executado: "200.00",
            disponivel: "800.00", // 20% -> Verde
          },
        ]),
      });
    });

    await page.goto("/sgd/execucao");

    const linhaPassagens = page.getByTestId("rubrica-linha-passagens");
    const badgeVermelho = linhaPassagens.getByTestId("semaforo-rubrica");
    await expect(badgeVermelho).toBeVisible();
    await expect(badgeVermelho).toHaveAttribute("data-nivel", "vermelho");
    await expect(badgeVermelho).toContainText("Vermelho");
    await expect(badgeVermelho).toContainText("95.0%");

    const linhaDiarias = page.getByTestId("rubrica-linha-diarias");
    const badgeAmarelo = linhaDiarias.getByTestId("semaforo-rubrica");
    await expect(badgeAmarelo).toBeVisible();
    await expect(badgeAmarelo).toHaveAttribute("data-nivel", "amarelo");
    await expect(badgeAmarelo).toContainText("Amarelo");
    await expect(badgeAmarelo).toContainText("75.0%");

    const linhaCombustivel = page.getByTestId("rubrica-linha-combustivel");
    const badgeVerde = linhaCombustivel.getByTestId("semaforo-rubrica");
    await expect(badgeVerde).toBeVisible();
    await expect(badgeVerde).toHaveAttribute("data-nivel", "verde");
    await expect(badgeVerde).toContainText("Verde");
    await expect(badgeVerde).toContainText("20.0%");
  });

  test("relatório de custo por atividade permite navegar até a lista de demandas daquela atividade", async ({
    page,
  }) => {
    await page.route(PAINEL_API, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.route(CUSTO_API, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            acao_id: 10,
            acao_numero: "2.1",
            acao_descricao: "Assistência Técnica em UPFs Agroecológicas",
            demandas: 3,
            estimado: "4500.00",
            autorizado: "4000.00",
            pago: "3800.00",
            atividades: [
              {
                atividade_id: 42,
                atividade_titulo: "Oficina de Manejo Sustentável",
                demandas: 3,
                estimado: "4500.00",
                autorizado: "4000.00",
                pago: "3800.00",
              },
            ],
          },
        ]),
      });
    });

    await page.goto("/sgd/execucao");

    // Alterna para a aba de Custo por Atividade
    const tabCusto = page.getByTestId("tab-custo-atividades");
    await tabCusto.click();

    await expect(page.getByText("Assistência Técnica em UPFs Agroecológicas")).toBeVisible();
    await expect(page.getByText("Oficina de Manejo Sustentável")).toBeVisible();

    const linkDemandas = page.getByTestId("link-demandas-42");
    await expect(linkDemandas).toBeVisible();
    const href = await linkDemandas.getAttribute("href");
    expect(href).toBe("/sgd/demandas?atividade=42");
  });

  test("exportar CSV com filtro de território e período ativo gera arquivo com o conteúdo esperado", async ({
    page,
  }) => {
    await page.route(PAINEL_API, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    let urlChamadaExport: string | null = null;
    await page.route(EXPORTAR_API, async (route) => {
      urlChamadaExport = route.request().url();
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/csv; charset=utf-8-sig",
          "Content-Disposition": 'attachment; filename="demandas_exportadas.csv"',
        },
        body: "ID,Título,Status,Território\n101,Demanda Campo,Autorizada,Sertão do São Francisco\n",
      });
    });

    await page.goto("/sgd/execucao");

    // Preenche filtros: Território e Período Inicial
    const filtroTerritorio = page.getByRole("combobox", { name: "Território" });
    await filtroTerritorio.click();
    await page.getByRole("option", { name: "Sertão do São Francisco" }).click();

    await page.getByLabel("Data inicial").fill("2026-03-01");

    // Dispara exportação CSV e aguarda download
    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("exportar-csv-btn").click();

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("demandas_exportadas.csv");

    // Valida que os filtros foram aplicados na requisição
    expect(urlChamadaExport).not.toBeNull();
    const parsedUrl = new URL(urlChamadaExport!);
    expect(parsedUrl.searchParams.get("formato")).toBe("csv");
    expect(parsedUrl.searchParams.get("territorio")).toBe("12");
    expect(parsedUrl.searchParams.get("periodo_inicio")).toBe("2026-03-01");
  });
});
