import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #467 — Ajustes de navegação, textos e acessibilidade, contra o backend real
 * e só leitura. O atalho do recurso extra no formulário da solicitação está em
 * `montar-demanda.spec.ts`, com a fixture da montagem.
 */

const SLOT_DO_CABECALHO = "#appshell-page-header-slot";

test.describe("Cabeçalhos, nomes e textos (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("cada tela diz no cabeçalho onde se está, em vez de só \"SGP\" ou \"SGD\"", async ({ page }) => {
    // A visão "Todas", para ter uma demanda qualquer para abrir em Editar.
    const lista = page.waitForResponse((r) => {
      const url = new URL(r.url());
      return url.pathname === "/api/v1/sgd/demandas/" && !url.searchParams.has("aguardando_minha_acao");
    });
    await page.goto("/sgd/demandas?visao=todas");
    await expect(page.locator(SLOT_DO_CABECALHO)).toHaveText("Demandas");
    const { results } = (await (await lista).json()) as { results: { id: number }[] };
    expect(results.length, "o seed tem demandas").toBeGreaterThan(0);

    for (const [url, titulo] of [
      ["/sgd/demandas/nova", "Nova demanda"],
      [`/sgd/demandas/${results[0].id}/editar`, "Editar demanda"],
      ["/sgd/remanejamentos", "Pedidos de recurso extra"],
      ["/sgp/orcamento/remanejamentos/novo", "Novo remanejamento"],
      ["/sgp/orcamento/remanejamentos", "Histórico de remanejamentos"],
    ] as const) {
      await page.goto(url);
      await expect(page.locator(SLOT_DO_CABECALHO), url).toHaveText(titulo);
    }
  });

  test("\"Fila de Remanejamentos\" passou a \"Pedidos de recurso extra\" no SGD", async ({ page }) => {
    await page.goto("/sgd");
    await expect(page.getByTestId("sgd-remanejamentos")).toContainText("Pedidos de recurso extra");
    await page.getByTestId("sgd-remanejamentos").click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Pedidos de recurso extra");
    await expect(page.getByText("Fila de Remanejamentos")).toHaveCount(0);
  });

  test("calendário: \"Novembro de 2026\", com só a primeira letra em maiúscula", async ({ page }) => {
    await page.goto("/sgp/atividades/calendario?data=2026-11-15");
    await expect(page.getByTestId("calendario-periodo")).toHaveText("Novembro de 2026");
    await expect(page.getByTestId("calendario-periodo")).toHaveCSS("text-transform", "none");
  });

  test("home do SGP: descrições inteiras e contagem de UFPAs sem \"—\" solto", async ({ page }) => {
    const contagem = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/sgp/ufpas/");
    await page.goto("/sgp");
    const { count } = (await (await contagem).json()) as { count: number };
    const card = page.getByTestId("sgp-hub-card-ufpas");
    await expect(card).toContainText(count.toLocaleString("pt-BR"));
    await expect(card).not.toContainText("—");
    const descricao = card.getByText("Cadastro de famílias e Unidades Familiares de Produção Agropecuária (UFPA).");
    await expect(descricao).toBeVisible();
    // Sem corte: a altura do texto comporta todo o conteúdo.
    expect(await descricao.evaluate((el) => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
  });

  test("o botão Sair tem o nome acessível \"Sair\"", async ({ page }) => {
    await page.goto("/sgp");
    await expect(page.getByRole("button", { name: "Sair", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Saindo/ })).toHaveCount(0);
  });
});

test.describe("Paginação no celular (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp"), viewport: { width: 390, height: 844 } });

  test("os controles quebram linha e não passam da largura da tela", async ({ page }) => {
    await page.goto("/sgp/atividades");
    const controles = page.getByTestId("paginacao-controles");
    await expect(controles).toBeVisible();
    const caixa = await controles.boundingBox();
    expect(caixa).not.toBeNull();
    expect(caixa!.x + caixa!.width).toBeLessThanOrEqual(390);
    await expect(page.getByRole("combobox", { name: "Itens por página" })).toBeVisible();
  });
});

test.describe("Login", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("o texto institucional fala do Projeto Dom Hélder Câmara III", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto("/login");
    await expect(page.getByText("Plataforma do Projeto Dom Hélder Câmara III no semiárido brasileiro.")).toBeVisible();
    await expect(page.getByText(/Programa de Desenvolvimento Humano/)).toHaveCount(0);
  });
});
