import { expect, test, type Page } from "@playwright/test";
import {
  criarAlertasOrcamentoFixture,
  removerAlertasOrcamentoFixture,
  type AlertasOrcamentoFixture,
} from "./helpers/alertasOrcamentoFixture";
import { abrirComApi } from "./helpers/apiReal";
import { storageStatePath } from "./helpers/users";

/**
 * #403 (AJ-FE-07) — Alertas orçamentários e parâmetros globais, contra o
 * backend real: `GET /sgp/orcamento/alertas/` e `/system-config/`. Os alertas
 * são de pool, abertos pelos services do backend (ver a fixture).
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
    // O alvo pelo nome (#423, item 5): o território do pool, e não "Pool · Diárias".
    await expect(vermelho).toContainText(`${fx.vermelho.alvo} · ${fx.vermelho.rubrica}`);
    await expect(vermelho).toContainText("Pool territorial");
    await expect(alerta(page, fx.subexecucao.id)).toContainText(`Nacional · ${fx.subexecucao.rubrica}`);
    await expect(alerta(page, fx.subexecucao.id)).toContainText("Pool nacional");
    await expect(vermelho).toContainText("Semáforo");
    await expect(vermelho).toContainText("Vermelho");
    await expect(vermelho).toContainText("96,5%");
    await expect(alerta(page, fx.remanejamento.id)).toContainText("Remanejamento excessivo");
    await expect(alerta(page, fx.subexecucao.id)).toContainText("Subexecução");
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

  test("mostra os valores gravados, inclusive os booleanos e inteiros que o backend devolve já convertidos", async ({ page }) => {
    await page.goto("/admin/configuracoes/sgp/parametros-orcamento");
    await expect(page.getByTestId("parametros-orcamento")).toBeVisible();

    const controle = (chave: string) => page.locator(`#parametro-${chave}`);
    const ligado = (valor: string) => (valor === "True" ? "true" : "false");
    await expect(controle("budget_limit_period")).toHaveValue(fx.parametros.budget_limit_period);
    await expect(controle("budget_limit_carry_over")).toHaveValue(ligado(fx.parametros.budget_limit_carry_over));
    await expect(controle("budget_overallocation_allowed")).toHaveValue(
      ligado(fx.parametros.budget_overallocation_allowed),
    );
    for (const chave of ["budget_subexec_alert_months", "budget_subexec_min_pct", "budget_transfer_alert_pct"]) {
      await expect(controle(chave)).toHaveValue(fx.parametros[chave]);
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

  /**
   * O backend valida as faixas desde a #423 (item 6). As da tela
   * (`PARAMETROS` em `lib/parametrosOrcamento.ts`) precisam ser as mesmas: um
   * valor que a tela aceita e o servidor recusa só aparece depois do Salvar.
   * Os PATCH abaixo são recusados, então nada é gravado.
   */
  test("as faixas da tela são as que o backend aceita", async ({ page }) => {
    const origem = await abrirComApi(page, "/admin/configuracoes/sgp/parametros-orcamento");
    const patch = (chave: string, valor: string) =>
      page.evaluate(
        async ({ url, valor }) => {
          const sessao = await (await fetch("/api/auth/session")).json();
          const res = await fetch(url, {
            method: "PATCH",
            headers: { Authorization: `Bearer ${sessao.accessToken}`, "Content-Type": "application/json" },
            body: JSON.stringify({ valor }),
          });
          return { status: res.status, corpo: await res.json() };
        },
        { url: `${origem}/api/v1/system-config/${chave}/`, valor },
      );

    const faixas: [string, number, number][] = [
      ["budget_subexec_alert_months", 1, 24],
      ["budget_subexec_min_pct", 1, 100],
      ["budget_transfer_alert_pct", 1, 100],
    ];
    for (const [chave, min, max] of faixas) {
      for (const fora of [min - 1, max + 1]) {
        const { status, corpo } = await patch(chave, String(fora));
        expect(status, `${chave}=${fora}`).toBe(400);
        expect(JSON.stringify(corpo), `${chave}=${fora}`).toContain("valor");
      }
    }
    const periodo = await patch("budget_limit_period", "anual");
    expect(periodo.status).toBe(400);
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
