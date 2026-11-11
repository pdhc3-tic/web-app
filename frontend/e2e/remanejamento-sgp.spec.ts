import { expect, test, type Page, type Route } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #402 (AJ-FE-06) — Simulador de remanejamento: a UGP preenche origem,
 * destino e valor, vê o antes/depois com a mudança de faixa e confirma com
 * o mesmo payload. Se o saldo mudar entre a simulação e a confirmação, o
 * backend responde `INSUFFICIENT_BALANCE` e a tela pede nova simulação.
 *
 * E2E com `page.route`: isolamos a sequência (sem dependência de pools
 * seeded e permissões cruzadas). O payload da confirmação é inspecionado
 * para confirmar que é igual ao simulado.
 */

test.describe.configure({ mode: "serial" });

const POOLS = [
  {
    id: 10,
    rubrica: { id: 1, nome: "Diárias", slug: "diarias" },
    nivel: "estadual",
    estado: { id: 1, sigla: "PB", nome: "Paraíba" },
    territorio: null,
    saldo_disponivel: "5000.00",
    valor_alocado: "5000.00",
    valor_comprometido: "0.00",
    valor_executado: "0.00",
    percentual_comprometido: "0.00",
    semaforo: "verde",
  },
  {
    id: 20,
    rubrica: { id: 1, nome: "Diárias", slug: "diarias" },
    nivel: "estadual",
    estado: { id: 2, sigla: "RN", nome: "Rio Grande do Norte" },
    territorio: null,
    saldo_disponivel: "500.00",
    valor_alocado: "5000.00",
    valor_comprometido: "4500.00",
    valor_executado: "0.00",
    percentual_comprometido: "90.00",
    semaforo: "vermelho",
  },
];

const SIMULACAO_VALIDA = {
  origem: {
    saldo_antes: "5000.00",
    saldo_depois: "4000.00",
    percentual_antes: "0.00",
    percentual_depois: "20.00",
    percentual_execucao_antes: "0.00",
    percentual_execucao_depois: "0.00",
    faixa_antes: "verde",
    faixa_depois: "verde",
  },
  destino: {
    saldo_antes: "500.00",
    saldo_depois: "1500.00",
    percentual_antes: "90.00",
    percentual_depois: "75.00",
    percentual_execucao_antes: "0.00",
    percentual_execucao_depois: "0.00",
    faixa_antes: "vermelho",
    faixa_depois: "amarelo",
  },
};

async function mockPools(page: Page) {
  await page.route("**/api/v1/sgp/orcamento/painel/*", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(POOLS),
    });
  });
}

type Captura = { simular: unknown[]; confirmar: unknown[] };

async function mockSimulacao(
  page: Page,
  resposta: unknown,
  respostaConfirmar: { status: number; body: unknown } = {
    status: 201,
    body: [{ id: 1 }],
  },
): Promise<Captura> {
  const captura: Captura = { simular: [], confirmar: [] };
  await page.route(
    "**/api/v1/sgp/orcamento/remanejamentos/simular/",
    async (route: Route) => {
      captura.simular.push(JSON.parse(route.request().postData() ?? "{}"));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(resposta),
      });
    },
  );
  await page.route(
    "**/api/v1/sgp/orcamento/remanejamentos/",
    async (route: Route) => {
      captura.confirmar.push(JSON.parse(route.request().postData() ?? "{}"));
      await route.fulfill({
        status: respostaConfirmar.status,
        contentType: "application/json",
        body: JSON.stringify(respostaConfirmar.body),
      });
    },
  );
  return captura;
}

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

async function preencher(page: Page) {
  await page.goto("/sgp/orcamento/remanejamentos/novo");
  await expect(page.getByTestId("remanejamento-form")).toBeVisible();

  await escolher(page, "remanejamento-origem", /Paraíba/);
  await escolher(page, "remanejamento-destino", /Rio Grande do Norte/);
  await page.getByLabel("Valor (R$)").fill("1000");
  await page.getByLabel("Justificativa").fill("Equilibrar RN.");
}

test.describe("UGP — novo remanejamento", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("simula e vê o antes/depois com mudança de faixa no destino", async ({ page }) => {
    await mockPools(page);
    await mockSimulacao(page, SIMULACAO_VALIDA);

    await preencher(page);
    await page.getByTestId("remanejamento-simular").click();

    const simulacao = page.getByTestId("remanejamento-simulacao");
    await expect(simulacao).toBeVisible();
    await expect(page.getByTestId("impacto-origem-saldo-antes")).toContainText("5.000,00");
    await expect(page.getByTestId("impacto-origem-saldo-depois")).toContainText("4.000,00");
    await expect(page.getByTestId("impacto-destino-saldo-depois")).toContainText("1.500,00");
    await expect(page.getByTestId("impacto-destino-mudou-faixa")).toBeVisible();
  });

  test("confirmar usa exatamente o payload simulado", async ({ page }) => {
    await mockPools(page);
    const captura = await mockSimulacao(page, SIMULACAO_VALIDA);

    await preencher(page);
    await page.getByTestId("remanejamento-simular").click();
    await expect(page.getByTestId("remanejamento-simulacao")).toBeVisible();

    await page.getByTestId("remanejamento-confirmar").click();

    await expect
      .poll(() => captura.confirmar.length, { timeout: 5_000 })
      .toBe(1);
    expect(captura.confirmar[0]).toEqual(captura.simular.at(-1));
  });

  test("alterar o formulário depois da simulação cancela a confirmação", async ({ page }) => {
    await mockPools(page);
    await mockSimulacao(page, SIMULACAO_VALIDA);

    await preencher(page);
    await page.getByTestId("remanejamento-simular").click();
    await expect(page.getByTestId("remanejamento-confirmar")).toBeEnabled();

    await page.getByLabel("Valor (R$)").fill("2000");
    await expect(page.getByTestId("remanejamento-simulacao")).toHaveCount(0);
  });

  test("confirmar com INSUFFICIENT_BALANCE pede nova simulação", async ({ page }) => {
    await mockPools(page);
    await mockSimulacao(page, SIMULACAO_VALIDA, {
      status: 400,
      body: { code: "INSUFFICIENT_BALANCE", message: "Saldo insuficiente." },
    });

    await preencher(page);
    await page.getByTestId("remanejamento-simular").click();
    await page.getByTestId("remanejamento-confirmar").click();

    await expect(page.getByTestId("remanejamento-erro")).toContainText(
      "O saldo mudou entre a simulação e a confirmação",
    );
    await expect(page.getByTestId("remanejamento-simulacao")).toHaveCount(0);
  });
});
