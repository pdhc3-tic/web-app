import { expect, test } from "@playwright/test";
import { criarMetaSemSubmetas, removerMetaSemSubmetas, type MetaSemSubmetas } from "./helpers/submetaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #431, revisão do PR #434 — Meta com mais Submetas do que cabem numa página
 * da API.
 *
 * `GET /sgp/submetas/?meta=` é paginada, e a Meta não tem limite de Submetas.
 * Lendo só a primeira página, a Submeta nova ficava fora da lista e do seletor
 * da Ação, e a sugestão de número repetia um que já existia. A Meta do teste
 * nasce com 200 Submetas (o teto de uma página da rota): a 201ª, cadastrada
 * pela tela, cai na segunda.
 */

const EXISTENTES = 200;
let meta: MetaSemSubmetas;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  meta = criarMetaSemSubmetas(EXISTENTES);
});

test.afterAll(() => {
  removerMetaSemSubmetas();
});

test.describe("UGP — Meta com mais de uma página de Submetas", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a Submeta nova, além da primeira página, aparece na lista e no seletor da Ação, e o número seguinte avança", async ({
    page,
  }) => {
    const nova = `${meta.numero}.${EXISTENTES + 1}`;
    // Leitura das Submetas atrasada: o formulário não pode abrir com a lista
    // incompleta, e um cadastro logo depois de outro não pode esperar a releitura.
    await page.route("**/api/v1/sgp/submetas/?*", async (route) => {
      if (route.request().method() === "GET") await new Promise((r) => setTimeout(r, 2_000));
      await route.continue();
    });
    await page.goto(`/sgp/metas/${meta.id}`);
    await expect(page.getByTestId("meta-detalhe-page")).toBeVisible();
    await expect(page.getByTestId("submeta-nova-btn")).toBeDisabled();
    await expect(page.getByTestId("submetas-secao")).toContainText(`${EXISTENTES} submetas`);
    await expect(page.getByTestId("submeta-nova-btn")).toBeEnabled();

    // A sugestão parte da lista inteira: 7.201, e não um número já usado.
    await page.getByTestId("submeta-nova-btn").click();
    await expect(page.getByTestId("submeta-form-numero")).toHaveValue(nova);
    await page.getByTestId("submeta-form-titulo").fill("Além da primeira página (E2E-431)");
    const criada = page.waitForResponse(
      (r) => r.url().includes("/api/v1/sgp/submetas/") && r.request().method() === "POST",
    );
    await page.getByTestId("submeta-form-submit").click();
    const resposta = await criada;
    expect(resposta.status()).toBe(201);
    const { id } = (await resposta.json()) as { id: number };

    // Na lista, sem recarregar e sem esperar a releitura (atrasada), e na contagem.
    await expect(page.getByTestId(`submeta-${id}`)).toContainText("Além da primeira página (E2E-431)", { timeout: 1_500 });
    await expect(page.getByTestId("submetas-secao")).toContainText(`${EXISTENTES + 1} submetas`);

    // Um segundo cadastro aberto já, com a releitura ainda em curso, sugere o próximo número.
    await page.getByTestId("submeta-nova-btn").click();
    await expect(page.getByTestId("submeta-form-numero")).toHaveValue(`${meta.numero}.${EXISTENTES + 2}`);
    await page.getByRole("button", { name: "Cancelar" }).click();

    // No seletor da Ação.
    await page.getByTestId("acao-nova-btn").click();
    const campo = page.getByTestId("acao-form-submeta");
    await campo.locator('button[role="combobox"]').click();
    await expect(campo.getByRole("option", { name: `${nova} — Além da primeira página (E2E-431)` })).toBeAttached();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Cancelar" }).click();

    // E o cadastro seguinte já sugere o próximo.
    await page.getByTestId("submeta-nova-btn").click();
    await expect(page.getByTestId("submeta-form-numero")).toHaveValue(`${meta.numero}.${EXISTENTES + 2}`);

    // Depois de recarregar, continua lá.
    await page.reload();
    await expect(page.getByTestId(`submeta-${id}`)).toBeVisible();
  });
});
