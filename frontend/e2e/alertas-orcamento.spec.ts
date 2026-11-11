import { expect, test, type Page } from "@playwright/test";
import {
  criarAlertasOrcamentoFixture,
  removerAlertasOrcamentoFixture,
  type AlertasOrcamentoFixture,
} from "./helpers/alertasOrcamentoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #403 (AJ-FE-07) — Alertas orçamentários e parâmetros globais, contra o
 * backend real: `GET /sgp/orcamento/alertas/` e `/system-config/`.
 */

let fx: AlertasOrcamentoFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarAlertasOrcamentoFixture();
});

test.afterAll(() => {
  removerAlertasOrcamentoFixture(fx?.parametros);
});

const CHAVE = "budget_subexec_min_pct";
const painel = (page: Page) => page.getByTestId("painel-alertas-orcamento");
const alerta = (page: Page, id: number) => page.getByTestId(`alerta-orcamento-${id}`);

test.describe("UGP — painel de alertas", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("aparece no Painel de Orçamento com tipo, faixa e percentual", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await expect(painel(page)).toBeVisible();

    const vermelho = alerta(page, fx.vermelho.id);
    await expect(vermelho).toContainText(fx.vermelho.rubrica);
    await expect(vermelho).toContainText("Semáforo");
    await expect(vermelho).toContainText("Vermelho");
    await expect(vermelho).toContainText("96,5%");
    await expect(alerta(page, fx.remanejamento.id)).toContainText("Remanejamento excessivo");
  });

  test("filtra por tipo e por faixa pelo servidor", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    await expect(alerta(page, fx.vermelho.id)).toBeVisible();

    const porTipo = page.waitForResponse((r) => new URL(r.url()).searchParams.get("tipo") === "subexecucao");
    await page.getByTestId("alertas-orcamento-filtro-tipo").selectOption("subexecucao");
    await porTipo;
    await expect(alerta(page, fx.subexecucao.id)).toBeVisible();
    await expect(alerta(page, fx.vermelho.id)).toHaveCount(0);
    await expect(
      painel(page).locator('[data-testid^="alerta-orcamento-"]:not([data-tipo="subexecucao"])'),
    ).toHaveCount(0);

    await page.getByTestId("alertas-orcamento-filtro-tipo").selectOption("");
    const porFaixa = page.waitForResponse((r) => new URL(r.url()).searchParams.get("faixa") === "vermelho");
    await page.getByTestId("alertas-orcamento-filtro-faixa").selectOption("vermelho");
    await porFaixa;
    await expect(alerta(page, fx.vermelho.id)).toBeVisible();
    await expect(alerta(page, fx.subexecucao.id)).toHaveCount(0);
    await expect(
      painel(page).locator('[data-testid^="alerta-orcamento-"]:not([data-faixa="vermelho"])'),
    ).toHaveCount(0);
  });

  test("aparece também na home do SGD", async ({ page }) => {
    await page.goto("/sgd");
    await expect(painel(page)).toBeVisible();
    await expect(alerta(page, fx.vermelho.id)).toBeVisible();
  });
});

test.describe("Super Admin — parâmetros do orçamento", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("a tela lista os seis parâmetros, a partir de Configurações", async ({ page }) => {
    await page.goto("/admin/configuracoes");
    await page.getByTestId("configuracao-card-parametros-orcamento").click();
    await expect(page).toHaveURL(/\/admin\/configuracoes\/sgp\/parametros-orcamento/);

    for (const chave of [
      "budget_limit_period",
      "budget_limit_carry_over",
      "budget_overallocation_allowed",
      "budget_subexec_alert_months",
      "budget_subexec_min_pct",
      "budget_transfer_alert_pct",
    ]) {
      await expect(page.getByTestId(`parametro-${chave}`)).toBeVisible();
    }
  });

  test("valida tipo e faixa antes de salvar", async ({ page }) => {
    await page.goto("/admin/configuracoes/sgp/parametros-orcamento");
    const campo = page.getByTestId(`parametro-${CHAVE}`).getByRole("textbox");
    const salvar = page.getByTestId(`parametro-salvar-${CHAVE}`);
    await expect(salvar).toBeDisabled();

    await campo.fill("abc");
    await expect(page.getByTestId(`parametro-erro-${CHAVE}`)).toHaveText("Informe um número inteiro.");
    await expect(salvar).toBeDisabled();

    await campo.fill("150");
    await expect(page.getByTestId(`parametro-erro-${CHAVE}`)).toHaveText("Informe um valor entre 1 e 100.");
    await expect(salvar).toBeDisabled();
  });

  test("salva o valor e ele continua lá depois de recarregar", async ({ page }) => {
    await page.goto("/admin/configuracoes/sgp/parametros-orcamento");
    const linha = page.getByTestId(`parametro-${CHAVE}`);
    const novo = fx.parametros[CHAVE] === "65" ? "66" : "65";

    await linha.getByRole("textbox").fill(novo);
    await page.getByTestId(`parametro-salvar-${CHAVE}`).click();
    await expect(linha).toContainText("Última alteração em");
    await expect(page.getByTestId(`parametro-salvar-${CHAVE}`)).toBeDisabled();

    await page.reload();
    await expect(page.getByTestId(`parametro-${CHAVE}`).getByRole("textbox")).toHaveValue(novo);
  });
});

test.describe("UGP — parâmetros são do Super Admin", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a tela de parâmetros fica restrita", async ({ page }) => {
    await page.goto("/admin/configuracoes/sgp/parametros-orcamento");
    await expect(page.getByTestId("parametros-orcamento")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Parâmetros do orçamento" })).toHaveCount(0);
  });
});
