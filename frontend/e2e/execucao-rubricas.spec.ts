import fs from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import {
  criarExecucaoFixture,
  removerExecucaoFixture,
  type ExecucaoFixture,
} from "./helpers/execucaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Painel de execução por rubrica e custo por atividade (#297), contra o
 * backend de verdade: a fixture cria verbas e reservas com valores conhecidos
 * no Território RN e uma demanda autorizada (e2e/helpers/execucaoFixture.ts).
 */

let fx: ExecucaoFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarExecucaoFixture();
});

test.afterAll(() => {
  if (fx) removerExecucaoFixture(fx);
});

function linhaDaRubrica(page: Page, slug: string) {
  return page.getByTestId(`rubrica-linha-${slug}`);
}

test.describe("UGP — Painel de Execução por Rubrica e Custos (#297)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("painel por rubrica exibe os valores corretos para uma rubrica com movimentação conhecida", async ({
    page,
  }) => {
    await page.goto(`/sgd/execucao?territorio=${fx.territorioId}&atividade=${fx.atividade.id}`);

    const locacao = linhaDaRubrica(page, "locacao-veiculo");
    const celulas = locacao.getByRole("cell");
    // Rubrica · Solicitado · Autorizado · Executado · Disponível · Semáforo
    await expect(celulas.nth(0)).toHaveText("Locação de Veículo");
    await expect(celulas.nth(1)).toHaveText("R$ 800,00");
    await expect(celulas.nth(2)).toHaveText("R$ 800,00");
    await expect(celulas.nth(3)).toHaveText("R$ 2.000,00");
    await expect(celulas.nth(4)).toHaveText("R$ 7.497,00");
    await expect(locacao.getByTestId("semaforo-rubrica")).toHaveAttribute("data-nivel", "verde");
    await expect(locacao.getByTestId("semaforo-rubrica")).toContainText("7,8%");
  });

  test("rubrica com execução acima de 90% exibe o semáforo vermelho; entre 70% e 90%, o amarelo", async ({
    page,
  }) => {
    await page.goto(`/sgd/execucao?territorio=${fx.territorioId}`);

    // Semáforo vindo do backend (comprometido sobre o aprovado): nada foi
    // pago nas Diárias, e mesmo assim a verba está quase toda reservada.
    const vermelho = linhaDaRubrica(page, "diarias").getByTestId("semaforo-rubrica");
    await expect(vermelho).toHaveAttribute("data-nivel", "vermelho");
    await expect(vermelho).toContainText("Vermelho (95,0%)");

    const amarelo = linhaDaRubrica(page, "passagens-aereas").getByTestId("semaforo-rubrica");
    await expect(amarelo).toHaveAttribute("data-nivel", "amarelo");
    await expect(amarelo).toContainText("Amarelo (75,0%)");
    // A #297 pede a cor de acento do SGD (Terracota PDHC, #B05A2F) na atenção.
    await expect(amarelo).toHaveCSS("color", "rgb(176, 90, 47)");
  });

  test("relatório de custo por atividade permite navegar até a lista de demandas daquela atividade", async ({
    page,
  }) => {
    await page.goto(`/sgd/execucao?aba=atividades&territorio=${fx.territorioId}`);

    const linha = page.getByTestId(`atividade-linha-${fx.atividade.id}`);
    await expect(linha).toContainText(fx.atividade.titulo);
    await expect(linha.getByRole("cell").nth(1)).toHaveText("1");
    await expect(linha.getByRole("cell").nth(3)).toHaveText("R$ 800,00");

    await linha.getByRole("link", { name: "Ver demandas" }).click();

    await expect(page).toHaveURL(new RegExp(`/sgd/demandas\\?.*atividade=${fx.atividade.id}`));
    await expect(page).toHaveURL(new RegExp(`territorio=${fx.territorioId}`));
    const faixa = page.getByTestId("filtro-atividade-ativo");
    await expect(faixa).toContainText(fx.atividade.titulo);
    await expect(faixa).toContainText("com mais 1 filtro do painel");

    const tabela = page.getByTestId("demandas-tabela");
    await expect(tabela.getByText(fx.demanda.titulo)).toBeVisible();
    await expect(tabela.locator("tbody tr")).toHaveCount(1);

    // Voltar ao painel preserva a aba e o recorte.
    await faixa.getByRole("link", { name: "Voltar ao painel" }).click();
    await expect(page).toHaveURL(/\/sgd\/execucao\?/);
    await expect(page).toHaveURL(/aba=atividades/);
    await expect(page.getByTestId(`atividade-linha-${fx.atividade.id}`)).toBeVisible();
  });

  test("a entrega também leva à lista das demandas que compõem o seu custo", async ({ page }) => {
    await page.goto(`/sgd/execucao?aba=atividades&atividade=${fx.atividade.id}`);

    await page.getByTestId(`link-demandas-entrega-${fx.acaoId}`).click();

    await expect(page).toHaveURL(new RegExp(`acao=${fx.acaoId}`));
    await expect(page.getByTestId("filtro-atividade-ativo")).toContainText("da entrega");
    await expect(page.getByTestId("demandas-tabela").getByText(fx.demanda.titulo)).toBeVisible();
  });

  test("exportar CSV com filtro de território e período ativo gera arquivo com o conteúdo esperado", async ({
    page,
  }) => {
    await page.goto("/sgd/execucao");

    await page.getByRole("combobox", { name: "Território" }).click();
    await page.getByRole("option", { name: fx.territorioNome, exact: true }).click();
    const hoje = new Date().toLocaleDateString("en-CA");
    await page.getByLabel("Data inicial").fill(hoje);

    // Os filtros ficam na URL — sobrevivem ao recarregar e ao "voltar".
    await expect(page).toHaveURL(new RegExp(`territorio=${fx.territorioId}`));
    await expect(page).toHaveURL(new RegExp(`periodo_inicio=${hoje}`));

    const pedido = page.waitForRequest(/\/api\/v1\/sgd\/demandas\/exportar\//);
    const download = page.waitForEvent("download");
    await page.getByTestId("exportar-csv-btn").click();

    const url = new URL((await pedido).url());
    expect(url.searchParams.get("formato")).toBe("csv");
    expect(url.searchParams.get("territorio")).toBe(String(fx.territorioId));
    expect(url.searchParams.get("periodo_inicio")).toBe(hoje);

    const arquivo = await download;
    expect(arquivo.suggestedFilename()).toMatch(/^demandas_.*\.csv$/);
    const conteudo = fs.readFileSync((await arquivo.path())!, "utf8");
    expect(conteudo).toContain(fx.demanda.titulo);
  });
});

test.describe("ADT — sem acesso ao painel de execução (#297)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("vê o aviso de acesso restrito, sem chamar o painel", async ({ page }) => {
    let chamouPainel = false;
    page.on("request", (r) => {
      if (r.url().includes("/api/v1/sgd/painel/rubricas/")) chamouPainel = true;
    });

    await page.goto("/sgd/execucao");

    await expect(page.getByRole("alert").filter({ hasText: "Conteúdo restrito" })).toBeVisible();
    await expect(page.getByTestId("tabela-painel-rubricas")).toHaveCount(0);
    expect(chamouPainel).toBe(false);
  });
});
