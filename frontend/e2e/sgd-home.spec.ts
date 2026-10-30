import { expect, test, type Page } from "@playwright/test";
import {
  criarPainelSgdFixture,
  removerPainelSgdFixture,
  type PainelSgdFixture,
} from "./helpers/painelSgdFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #318 (SGD-FE-7) — Home do SGD: fila "Aguardando minha ação", alertas de
 * saldo e demandas paradas, de `GET /sgd/dashboard/` (BE-11), contra o
 * backend real.
 */

let fx: PainelSgdFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarPainelSgdFixture();
});

test.afterAll(() => {
  removerPainelSgdFixture();
});

const fila = (page: Page) => page.getByTestId("painel-fila");

/** Ids da fila na ordem em que aparecem na tela. */
async function idsDaFila(page: Page): Promise<number[]> {
  const testIds = await fila(page)
    .locator('[data-testid^="fila-item-"]')
    .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid") ?? ""));
  return testIds.map((t) => Number(t.replace("fila-item-", "")));
}

test.describe("Articulador Estadual (atua em RN)", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("a fila vem na ordem: tempo de espera, depois valor, com o selo de espera", async ({ page }) => {
    await page.goto("/sgd");
    await expect(fila(page).getByTestId(`fila-item-${fx.menor.id}`)).toBeVisible();

    const nossos = (await idsDaFila(page)).filter((id) =>
      [fx.antiga.id, fx.maior.id, fx.menor.id].includes(id),
    );
    // A mais antiga primeiro; no mesmo dia, o maior valor antes, mesmo tendo chegado depois.
    expect(nossos).toEqual([fx.antiga.id, fx.maior.id, fx.menor.id]);

    const esperaAntiga = page.getByTestId(`fila-espera-${fx.antiga.id}`).getByTestId("semaforo-badge");
    await expect(esperaAntiga).toHaveText("Há 12 dias");
    await expect(esperaAntiga).toHaveAttribute("data-nivel", "vermelho");
    const esperaMaior = page.getByTestId(`fila-espera-${fx.maior.id}`).getByTestId("semaforo-badge");
    await expect(esperaMaior).toHaveText("Há 2 dias");
    await expect(esperaMaior).toHaveAttribute("data-nivel", "verde");

    await expect(fila(page).getByTestId(`fila-item-${fx.maior.id}`)).toContainText("R$ 900,00");
  });

  test("alertas de saldo nas faixas vermelha e amarela, com link para a execução por rubrica", async ({
    page,
  }) => {
    await page.goto("/sgd");
    const alertas = page.getByTestId("painel-alertas");

    const vermelho = alertas.getByTestId(`alerta-alimentacao-refeicoes-${fx.metaId}-RN`);
    await expect(vermelho).toContainText("Alimentação");
    await expect(vermelho).toContainText("95% comprometido");
    await expect(vermelho.getByTestId("semaforo-badge")).toHaveAttribute("data-nivel", "vermelho");
    await expect(vermelho).toContainText("RN");

    const amarelo = alertas.getByTestId(`alerta-material-grafico-${fx.metaId}-RN`);
    await expect(amarelo.getByTestId("semaforo-badge")).toHaveAttribute("data-nivel", "amarelo");

    // A vermelha vem antes da amarela.
    const ordem = await alertas
      .locator('[data-testid^="alerta-"]')
      .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")));
    expect(ordem.indexOf(`alerta-alimentacao-refeicoes-${fx.metaId}-RN`)).toBeLessThan(
      ordem.indexOf(`alerta-material-grafico-${fx.metaId}-RN`),
    );

    await vermelho.getByRole("link").click();
    await expect(page).toHaveURL(
      new RegExp(`/sgd/execucao\\?rubrica=alimentacao-refeicoes&meta=${fx.metaId}$`),
    );
  });

  test("a demanda parada há 5+ dias úteis aparece com os dias e abre no painel", async ({ page }) => {
    await page.goto("/sgd");
    const parada = page.getByTestId("painel-paradas").getByTestId(`parada-item-${fx.antiga.id}`);
    await expect(parada).toContainText(fx.antiga.titulo);
    await expect(parada).toContainText(/\d+ dias úteis/);

    await parada.getByRole("link").click();
    await expect(page).toHaveURL(new RegExp(`/sgd/demandas\\?visao=todas&demanda=${fx.antiga.id}$`));
    await expect(page.getByTestId("demanda-painel")).toContainText(fx.antiga.titulo);
  });

  test("clicar num item da fila abre o painel de demandas com ele selecionado", async ({ page }) => {
    await page.goto("/sgd");
    await fila(page).getByTestId(`fila-item-${fx.maior.id}`).getByRole("link").click();

    await expect(page).toHaveURL(new RegExp(`/sgd/demandas\\?demanda=${fx.maior.id}$`));
    const painel = page.getByTestId("demanda-painel");
    await expect(painel).toContainText(fx.maior.titulo);
    await expect(painel.getByTestId("acao-pre-autorizar")).toBeVisible();
  });
});

test.describe("Articulador Estadual de outro estado (PE)", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("não vê na fila nem nos alertas o que é de RN", async ({ page }) => {
    await page.goto("/sgd");
    await expect(page.getByTestId("painel-sgd")).toBeVisible();
    await expect(page.getByTestId(`fila-item-${fx.antiga.id}`)).toHaveCount(0);
    await expect(page.getByTestId(`parada-item-${fx.antiga.id}`)).toHaveCount(0);
    await expect(page.getByTestId(`alerta-alimentacao-refeicoes-${fx.metaId}-RN`)).toHaveCount(0);
  });
});

test.describe("ADT (solicitante)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("sem pendências para ele, a fila e os alertas mostram o estado vazio", async ({ page }) => {
    await page.goto("/sgd");
    await expect(page.getByTestId("painel-sgd")).toBeVisible();
    // O solicitante não decide etapa nenhuma: a fila de aprovação é sempre vazia para ele.
    await expect(page.getByTestId("painel-fila-vazio")).toContainText("Nenhuma demanda aguardando você");
    await expect(page.getByTestId("painel-fila-total")).toHaveText("0");
    // As verbas da fixture são estaduais: fora do escopo territorial do ADT.
    await expect(page.getByTestId("painel-alertas-vazio")).toContainText("Nenhuma rubrica em alerta");
    // Os cards de submódulo continuam abaixo do painel.
    await expect(page.getByTestId("sgd-painel")).toBeVisible();
  });
});
