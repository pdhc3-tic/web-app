import { expect, test, type Page } from "@playwright/test";
import {
  criarLimitesFixture,
  definirSobrealocacao,
  removerLimitesFixture,
  type LimitesFixture,
} from "./helpers/limitesFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #400 — Gestão de limites de gasto (backend #385, PR #411), contra o backend
 * real. A UGP define e altera o padrão por perfil, cria e altera sobrescritas
 * individuais, consulta períodos passados e vê o pool e a soma quando a
 * sobrealocação está desligada. O ADT não entra.
 */

let fx: LimitesFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarLimitesFixture();
});

test.afterAll(() => {
  removerLimitesFixture(fx);
});

const celula = (page: Page, perfil: string, rubrica: string) =>
  page.getByTestId(`limites-celula-${perfil}-${rubrica}`);

/** "2027-01-01" → "01/01/2027". */
const br = (iso: string) => iso.split("-").reverse().join("/");

async function abrir(page: Page) {
  await page.goto("/sgp/orcamento/limites");
  await expect(page.getByTestId("limites-matriz")).toBeVisible();
}

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

async function salvar(page: Page) {
  const resposta = page.waitForResponse(
    (r) => r.url().includes("/api/v1/sgp/orcamento/limites/") && r.request().method() !== "GET",
  );
  await page.getByTestId("limite-salvar").click();
  return resposta;
}

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("chega pelo Painel de Orçamento e vê a matriz rubrica × perfil do período vigente", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await page.getByTestId("orcamento-ir-limites").click();
    await expect(page).toHaveURL(/\/sgp\/orcamento\/limites$/);

    await expect(page.getByTestId("limites-periodo-rotulo")).toHaveText(/trimestre de \d{4}/);
    await expect(page.getByTestId("limites-periodo")).toContainText("Vigente");
    const grafico = celula(page, "adt-acr", "material-grafico");
    await expect(grafico.getByTestId("limites-celula-valor")).toHaveText("R$ 1.500,00");
    await expect(grafico.getByTestId("limites-celula-acao")).toHaveText("Alterar");
  });

  test("define o padrão de um perfil numa rubrica sem padrão", async ({ page }) => {
    await abrir(page);
    const diarias = celula(page, "articulador-estadual", "diarias");
    await expect(diarias.getByTestId("limites-celula-valor")).toHaveText("Sem padrão");
    await diarias.getByTestId("limites-celula-acao").click();

    await page.getByTestId("limite-valor").fill("200000");
    const res = await salvar(page);
    expect(res.status()).toBe(201);
    await expect(diarias.getByTestId("limites-celula-valor")).toHaveText("R$ 2.000,00");
  });

  test("alterar um padrão em uso exige justificativa e vale a partir do próximo período", async ({ page }) => {
    await abrir(page);
    const grafico = celula(page, "adt-acr", "material-grafico");
    await grafico.getByTestId("limites-celula-acao").click();

    await page.getByTestId("limite-valor").fill("180000");
    await page.getByTestId("limite-salvar").click();
    await expect(page.getByTestId("limite-form")).toContainText("Obrigatória");

    await page.getByTestId("limite-justificativa").fill("Reajuste do material da campanha.");
    expect((await salvar(page)).status()).toBe(200);
    await expect(page.getByText(`vale a partir de ${br(fx.proximoInicio)}`)).toBeVisible();

    // No período vigente o valor antigo continua; o novo aparece no seguinte.
    await expect(grafico.getByTestId("limites-celula-valor")).toHaveText("R$ 1.500,00");
    await page.getByTestId("limites-periodo-seguinte").click();
    await expect(page.getByTestId("limites-somente-leitura")).toBeVisible();
    await expect(grafico.getByTestId("limites-celula-valor")).toHaveText("R$ 1.800,00");
    await expect(page.getByTestId("limites-celula-acao")).toHaveCount(0);
  });

  test("o período anterior fica só para consulta", async ({ page }) => {
    await abrir(page);
    await page.getByTestId("limites-periodo-anterior").click();
    await expect(page.getByTestId("limites-somente-leitura")).toBeVisible();
    await expect(page.getByTestId("limites-celula-acao")).toHaveCount(0);

    await page.getByRole("tab", { name: /Sobrescritas individuais/ }).click();
    await expect(page.getByTestId("limites-nova-sobrescrita")).toHaveCount(0);

    await page.getByTestId("limites-periodo-vigente").click();
    await expect(page.getByTestId("limites-periodo")).toContainText("Vigente");
    await expect(page.getByTestId("limites-nova-sobrescrita")).toBeVisible();
  });

  test("a linha nascida do padrão aparece como herdada do perfil", async ({ page }) => {
    await abrir(page);
    await page.getByRole("tab", { name: /Sobrescritas individuais/ }).click();
    const linha = page
      .getByTestId("limites-sobrescritas")
      .locator("tr", { hasText: fx.marina.nome })
      .filter({ hasText: "Material Gráfico" });
    await expect(linha.getByTestId("limite-precedencia")).toHaveText("Herdado do perfil");
  });

  test("cria uma sobrescrita: sem justificativa não envia; com ela, aparece como sobrescrita", async ({ page }) => {
    await abrir(page);
    await page.getByRole("tab", { name: /Sobrescritas individuais/ }).click();
    await page.getByTestId("limites-nova-sobrescrita").click();

    await page.getByTestId("limite-usuario").fill(fx.marina.nome.split(" ")[0]);
    await page.getByRole("option", { name: fx.marina.nome }).click();
    await escolher(page, "limite-rubrica", "Diárias");
    await page.getByTestId("limite-valor").fill("80000");

    let enviou = false;
    page.on("request", (r) => {
      if (r.url().includes("/orcamento/limites/") && r.method() === "POST") enviou = true;
    });
    await page.getByTestId("limite-salvar").click();
    await expect(page.getByTestId("limite-form")).toContainText("Obrigatória");
    expect(enviou).toBe(false);

    await page.getByTestId("limite-justificativa").fill("Agenda de campo extra no trimestre.");
    expect((await salvar(page)).status()).toBe(201);

    const linha = page
      .getByTestId("limites-sobrescritas")
      .locator("tr", { hasText: fx.marina.nome })
      .filter({ hasText: "Diárias" });
    await expect(linha.getByTestId("limite-precedencia")).toHaveText("Sobrescrito");
    await expect(linha).toContainText("R$ 800,00");
    await expect(linha).toContainText("Agenda de campo extra no trimestre.");
  });

  test("com a sobrealocação desligada, a recusa mostra a soma dos limites e o pool", async ({ page }) => {
    definirSobrealocacao(false);
    try {
      await abrir(page);
      await page.getByRole("tab", { name: /Sobrescritas individuais/ }).click();
      const linha = page
        .getByTestId("limites-sobrescritas")
        .locator("tr", { hasText: fx.marina.nome })
        .filter({ hasText: "Diárias" });
      await linha.getByTestId("limites-sobrescrita-alterar").click();

      await page.getByTestId("limite-valor").fill("5000000");
      await page.getByTestId("limite-justificativa").fill("Teste de teto do território.");
      expect((await salvar(page)).status()).toBe(400);

      const bloco = page.getByTestId("limite-sobrealocacao");
      await expect(bloco).toContainText("a sobrealocação está desligada");
      await expect(page.getByTestId("limite-sobrealocacao-pool")).toHaveText("R$ 7.000,00");
      await expect(page.getByTestId("limite-sobrealocacao-soma")).toContainText("R$ 5");
    } finally {
      definirSobrealocacao(true);
    }
  });
});

test.describe("ADT/ACR", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("não vê o atalho nem a tela de limites", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await expect(page.getByRole("heading", { name: "Painel de Orçamento" })).toBeVisible();
    await expect(page.getByTestId("orcamento-ir-limites")).toHaveCount(0);

    await page.goto("/sgp/orcamento/limites");
    await expect(page.getByText("Limites restritos")).toBeVisible();
    await expect(page.getByTestId("limites-matriz")).toHaveCount(0);
  });
});
