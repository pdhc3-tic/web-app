import { expect, test, type Page } from "@playwright/test";
import {
  criarDotacaoFixture,
  dotacaoNoBanco,
  ESTADO,
  removerDotacaoFixture,
  RUBRICA,
  TERRITORIO,
  TIPO_SOLICITACAO,
  type DotacaoFixture,
} from "./helpers/dotacaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Dotação nacional por rubrica (#438), contra o backend real.
 *
 * Os testes seguem a cadeia que a issue diz estar travada: sem pool nacional, a
 * Distribuição não tem teto e o SGD mostra saldo zero. Por isso a suíte é
 * serial: cada passo parte do que o anterior gravou pela tela, e a fixture só
 * monta a rubrica vazia e a demanda do ADT.
 *
 *   1. a Distribuição sem dotação aponta para a tela nova;
 *   2. a UGP lança a dotação (POST nacional) e distribui ao RN;
 *   3. o Articulador do RN repassa ao território;
 *   4. o ADT vê a verba do território no formulário de solicitação;
 *   5. a UGP ajusta (PATCH) e não consegue baixar abaixo do distribuído.
 *
 * O estado vazio do Painel (sem nenhum pool) é testado com a resposta do painel
 * trocada por uma lista vazia: não grava nada e não depende da cadeia acima.
 */

let fx: DotacaoFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarDotacaoFixture();
});

test.afterAll(() => {
  removerDotacaoFixture();
});

const DOTACAO = "100000"; // R$ 100.000,00, digitado em reais
const PARA_O_ESTADO = "40000";
const PARA_O_TERRITORIO = "30000";

/** O campo de dinheiro é mascarado a partir dos dígitos: "100000" vira "100000,00". */
function centavos(reais: string): string {
  return `${reais}00`;
}

async function escolherRubricaNaDistribuicao(page: Page): Promise<void> {
  await page.locator("#distribuicao-rubrica").click();
  await page.locator('li[role="option"]').filter({ hasText: new RegExp(`^${RUBRICA.nome}$`) }).click();
}

async function linhaDoDestino(page: Page, nome: string) {
  const linha = page.locator('[data-testid^="distribuicao-destino-"]').filter({ hasText: nome }).first();
  await expect(linha).toBeVisible();
  const id = (await linha.getAttribute("data-testid"))!.replace("distribuicao-destino-", "");
  return id;
}

async function distribuir(page: Page, destino: string, reais: string): Promise<void> {
  const id = await linhaDoDestino(page, destino);
  await page.getByTestId(`distribuicao-valor-${id}`).fill(centavos(reais));
  await page.getByTestId(`distribuicao-submit-${id}`).click();
  await page.getByTestId("distribuicao-confirmar").click();
  await expect(page.getByRole("status").first()).toContainText(/distribuído/i);
}

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a Distribuição sem dotação nacional leva à tela de dotação", async ({ page }) => {
    await page.goto("/sgp/orcamento/distribuicao");
    await expect(page.getByTestId("distribuicao-page")).toBeVisible();
    await escolherRubricaNaDistribuicao(page);

    await expect(page.getByTestId("distribuicao-sem-pai")).toContainText("ainda não tem dotação nacional");
    await page.getByTestId("distribuicao-ir-dotacao").click();
    await expect(page).toHaveURL(/\/sgp\/orcamento\/dotacao/);
    await expect(page.getByTestId("dotacao-page")).toBeVisible();
  });

  test("lança a dotação da rubrica e distribui ao estado", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await page.getByTestId("orcamento-ir-dotacao").click();
    await expect(page.getByTestId("dotacao-page")).toBeVisible();

    // As seis rubricas do orçamento aparecem para receber dotação.
    await expect(page.locator('[data-testid^="dotacao-rubrica-"]')).toHaveCount(6);

    const linha = page.getByTestId(`dotacao-rubrica-${RUBRICA.slug}`);
    await expect(linha).toContainText("Sem dotação lançada");
    await expect(page.getByTestId(`dotacao-submit-${RUBRICA.slug}`)).toHaveText("Lançar");

    await page.getByTestId(`dotacao-valor-${RUBRICA.slug}`).fill(centavos(DOTACAO));
    await page.getByTestId(`dotacao-submit-${RUBRICA.slug}`).click();
    await expect(page.getByTestId("dotacao-confirmacao")).toContainText(RUBRICA.nome);
    await page.getByTestId("dotacao-confirmar").click();

    await expect(page.getByRole("status").first()).toContainText(/lançada/i);
    await expect(linha).toContainText(/Dotação hoje: R\$\s*100\.000,00/);
    await expect(page.getByTestId(`dotacao-submit-${RUBRICA.slug}`)).toHaveText("Ajustar");
    expect(dotacaoNoBanco()).toBe("100000.00");

    // A Distribuição passa a ter teto e a UGP repassa ao RN.
    await page.getByTestId("dotacao-ir-distribuicao").click();
    await expect(page.getByTestId("distribuicao-page")).toBeVisible();
    await escolherRubricaNaDistribuicao(page);
    await expect(page.getByTestId("distribuicao-barra-saldo")).toBeVisible();
    await distribuir(page, `(${ESTADO.sigla})`, PARA_O_ESTADO);
  });
});

test.describe("Articulador do RN", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("repassa ao território o que o estado recebeu", async ({ page }) => {
    await page.goto("/sgp/orcamento/distribuicao");
    await expect(page.getByTestId("distribuicao-page")).toBeVisible();
    await escolherRubricaNaDistribuicao(page);
    await page.locator("#distribuicao-estado").click();
    await page.locator('li[role="option"]').filter({ hasText: new RegExp(`^${ESTADO.sigla}$`) }).click();

    await expect(page.getByTestId("distribuicao-barra-saldo")).toBeVisible();
    await distribuir(page, TERRITORIO.nome, PARA_O_TERRITORIO);
  });

  test("não lança dotação nacional", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await expect(page.getByTestId("orcamento-page")).toBeVisible();
    await expect(page.getByTestId("orcamento-ir-dotacao")).toHaveCount(0);

    await page.goto("/sgp/orcamento/dotacao");
    await expect(page.getByText("Dotação restrita")).toBeVisible();
    await expect(page.getByTestId("dotacao-rubricas")).toHaveCount(0);
  });
});

test.describe("ADT do território", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("vê a verba do território no formulário de solicitação do SGD", async ({ page }) => {
    await page.goto(`/sgd/demandas/${fx.demandaId}/editar`);
    await expect(page.getByTestId("montar-demanda")).toBeVisible();
    await page.getByTestId("solicitacao-adicionar").click();
    await page.locator("button#solicitacao-tipo").click();
    await page.getByRole("option", { name: TIPO_SOLICITACAO }).first().click();

    const territorial = page.getByTestId("saldo-territorial");
    await expect(territorial).toContainText(/Disponível:\s*R\$\s*30\.000,00/);
  });
});

/**
 * O Painel sem nenhum pool, como num banco em que a UGP ainda não lançou nada.
 * O banco do E2E já tem pools de outras specs, então a resposta real do painel
 * é trocada por uma lista vazia, mantendo os cabeçalhos (CORS) da resposta real.
 */
async function painelSemOrcamento(page: Page): Promise<void> {
  await page.route(
    (url) => url.pathname === "/api/v1/sgp/orcamento/painel/",
    async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const resposta = await route.fetch();
      await route.fulfill({ response: resposta, json: [] });
    },
  );
}

test.describe("Painel de Orçamento vazio", () => {
  test.describe("UGP", () => {
    test.use({ storageState: storageStatePath("ugp") });

    test("o estado vazio leva à dotação nacional", async ({ page }) => {
      await painelSemOrcamento(page);
      await page.goto("/sgp/orcamento");
      await expect(page.getByText("Nenhum orçamento lançado ainda")).toBeVisible();
      await page.getByTestId("orcamento-vazio-dotacao").click();
      await expect(page).toHaveURL(/\/sgp\/orcamento\/dotacao/);
      await expect(page.getByTestId("dotacao-page")).toBeVisible();
    });
  });

  test.describe("Articulador", () => {
    test.use({ storageState: storageStatePath("articuladorPB") });

    test("o estado vazio diz que a dotação é da UGP, sem botão", async ({ page }) => {
      await painelSemOrcamento(page);
      await page.goto("/sgp/orcamento");
      await expect(page.getByText("A UGP ainda não lançou a dotação nacional", { exact: false })).toBeVisible();
      await expect(page.getByTestId("orcamento-vazio-dotacao")).toHaveCount(0);
    });
  });
});

test.describe("UGP depois da distribuição", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("ajusta a dotação e não baixa abaixo do que já desceu ao estado", async ({ page }) => {
    await page.goto("/sgp/orcamento/dotacao");
    const linha = page.getByTestId(`dotacao-rubrica-${RUBRICA.slug}`);
    await expect(linha).toContainText(/distribuído aos estados: R\$\s*40\.000,00/);

    const campo = page.getByTestId(`dotacao-valor-${RUBRICA.slug}`);
    const botao = page.getByTestId(`dotacao-submit-${RUBRICA.slug}`);
    await campo.fill(centavos("39999"));
    await expect(botao).toBeDisabled();
    await expect(page.getByTestId(`dotacao-motivo-${RUBRICA.slug}`)).toContainText(/40\.000,00/);

    await campo.fill(centavos("120000"));
    await botao.click();
    await expect(page.getByTestId("dotacao-confirmacao")).toContainText(/\+\s*R\$\s*20\.000,00/);
    await page.getByTestId("dotacao-confirmar").click();

    await expect(linha).toContainText(/Dotação hoje: R\$\s*120\.000,00/);
    expect(dotacaoNoBanco()).toBe("120000.00");
  });
});
