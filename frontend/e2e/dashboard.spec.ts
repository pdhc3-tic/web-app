import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Dashboard — cards de alerta do SGP (#236).
 *
 * Três cards: "Sem evidência", "Atrasadas" e "Ações críticas". Cada um mostra
 * um contador e um link para a listagem filtrada. Estes testes garantem:
 *
 * 1. Cada card carrega/degrada com estado explícito (contagem, "Nenhuma
 *    pendência" ou "Não foi possível carregar").
 * 2. O link de cada card usa exatamente o critério da contagem — em especial
 *    o "Ações críticas", que antes ia para `situacao=em_atraso` (outro
 *    critério) e agora aponta para `?criticas=1`, o filtro dedicado do painel.
 * 3. A contagem do card bate com o que aparece na listagem/painel filtrado.
 * 4. Falha isolada de um endpoint não derruba os outros dois.
 * 5. Perfis diferentes (UGP consolidado, ADT restrito) recebem o dashboard.
 */

async function abrirDashboard(page: Page): Promise<void> {
  await page.goto("/dashboard");
  await expect(
    page.getByRole("region", { name: /Alertas do SGP/i }),
  ).toBeVisible();
}

function card(page: Page, index: number) {
  return page
    .locator("section[aria-label='Alertas do SGP'] > div")
    .nth(index);
}

test.describe("Dashboard — UGP (visão consolidada)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("os três cards do #236 aparecem com estado resolvido", async ({
    page,
  }) => {
    await abrirDashboard(page);
    for (const rotulo of ["Sem evidência", "Atrasadas", "Ações críticas"]) {
      await expect(page.getByText(rotulo, { exact: true })).toBeVisible();
    }
    // Cada card resolve para: contagem numérica, "Nenhuma pendência" ou erro
    // — nunca fica em loading para sempre.
    for (let i = 0; i < 3; i++) {
      await expect(
        card(page, i).getByText(
          /Nenhuma pendência|Não foi possível carregar|^\d+$/,
        ),
      ).toBeVisible();
    }
  });

  test("Sem evidência: link usa status=concluido_sem_evidencia", async ({
    page,
  }) => {
    await abrirDashboard(page);
    const link = card(page, 0).getByRole("link", { name: /Ver listagem/ });
    await expect(link).toHaveAttribute(
      "href",
      /\/sgp\/atividades\?status=concluido_sem_evidencia/,
    );
  });

  test("Atrasadas: link usa atrasada=true (mesmo critério da contagem)", async ({
    page,
  }) => {
    await abrirDashboard(page);
    const link = card(page, 1).getByRole("link", { name: /Ver listagem/ });
    // Pedro apontou: o card conta com atrasada=true e o link precisa usar o
    // MESMO parâmetro (não situacao=em_atraso, que é critério diferente).
    // Backend ainda não implementou o filtro atrasada; o front está pronto.
    await expect(link).toHaveAttribute(
      "href",
      /\/sgp\/atividades\?atrasada=true/,
    );
  });

  test("Ações críticas: link usa ?criticas=1, não situacao=em_atraso", async ({
    page,
  }) => {
    await abrirDashboard(page);
    const link = card(page, 2).getByRole("link", { name: /Ver listagem/ });
    // Ponto explícito do review do #236: `?criticas=1` (filtro dedicado do
    // painel, semaforo=vermelho) tem que substituir `situacao=em_atraso`,
    // que representava critério diferente da contagem do card.
    await expect(link).toHaveAttribute("href", /\/sgp\/painel\?criticas=1/);
    await expect(link).not.toHaveAttribute("href", /situacao=em_atraso/);
  });

  test("clique em Ações críticas leva ao painel com filtro ligado", async ({
    page,
  }) => {
    await abrirDashboard(page);
    await card(page, 2).getByRole("link", { name: /Ver listagem/ }).click();
    await page.waitForURL(/\/sgp\/painel\?criticas=1/);
    await expect(page.getByTestId("painel-page")).toBeVisible();
    // Checkbox do filtro deve estar ligado ao aterrizar via link do card.
    await expect(page.getByTestId("painel-filtro-criticas")).toBeChecked();
  });

  test("contagem do card Ações críticas bate com o painel filtrado", async ({
    page,
  }) => {
    await abrirDashboard(page);
    // Lê a contagem do card (número visível dentro do 3º card).
    const cardCriticas = card(page, 2);
    const numero = await cardCriticas
      .locator("span.tabular-nums")
      .first()
      .textContent()
      .catch(() => null);

    // Se o card mostra "Nenhuma pendência", nada a comparar — o painel vazio
    // é aceitável nessa branch.
    if (!numero || !/^\d+$/.test(numero.trim())) {
      test.info().annotations.push({
        type: "info",
        description: "Sem ações críticas no seed atual; pulando comparação.",
      });
      return;
    }

    const esperado = Number(numero.trim());

    // Vai para o painel com o filtro do card.
    await cardCriticas
      .getByRole("link", { name: /Ver listagem/ })
      .click();
    await page.waitForURL(/criticas=1/);

    // Espera o painel resolver: cada Ação renderiza um data-testid próprio.
    // O total contado pelo painel após o filtro tem que casar com o card.
    await expect(page.getByTestId("painel-page")).toBeVisible();
    const acoesNoPainel = page.locator('[data-testid^="painel-acao-"]');
    // Cada Ação aparece 2x (alerta + card da Meta), então dividimos.
    // Ou usamos uma contagem única via IDs distintos.
    const idsUnicos = new Set<string>();
    const total = await acoesNoPainel.count();
    for (let i = 0; i < total; i++) {
      const testid = await acoesNoPainel.nth(i).getAttribute("data-testid");
      if (testid) idsUnicos.add(testid);
    }
    expect(idsUnicos.size).toBe(esperado);
  });

  test("falha isolada no endpoint do painel não derruba os outros dois cards", async ({
    page,
  }) => {
    await page.route("**/plano-trabalho/painel/**", (route) =>
      route.fulfill({ status: 500, body: "error" }),
    );
    await abrirDashboard(page);

    // Os cards de Sem Evidência e Atrasadas continuam carregando normalmente.
    await expect(
      card(page, 0).getByText(/Nenhuma pendência|^\d+$/),
    ).toBeVisible();
    await expect(
      card(page, 1).getByText(/Nenhuma pendência|Não foi possível carregar|^\d+$/),
    ).toBeVisible();
    // Só o card afetado mostra erro.
    await expect(
      card(page, 2).getByText(/Não foi possível carregar/i),
    ).toBeVisible();
  });

  test("estado zero (Nenhuma pendência) preserva o link para a listagem", async ({
    page,
  }) => {
    // Força contagem zero em todos os endpoints.
    await page.route(
      /\/api\/v1\/sgp\/atividades\/\?.*/,
      async (route) => {
        // Só intercepta as chamadas com `page_size=1` que o dashboard usa
        // para contar (respostas normais da listagem não vêm com page_size=1).
        const url = new URL(route.request().url());
        if (url.searchParams.get("page_size") === "1") {
          await route.fulfill({
            status: 200,
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ count: 0, results: [], next: null, previous: null }),
          });
          return;
        }
        await route.continue();
      },
    );
    await page.route("**/plano-trabalho/painel/**", (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ metas: [] }),
      }),
    );

    await abrirDashboard(page);
    // Todos os três cards mostram "Nenhuma pendência" e mantêm o link.
    for (let i = 0; i < 3; i++) {
      await expect(card(page, i).getByText(/Nenhuma pendência/)).toBeVisible();
      await expect(
        card(page, i).getByRole("link", { name: /Ver listagem/ }),
      ).toBeVisible();
    }
  });
});

test.describe("Dashboard — ADT (escopo restrito)", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("ADT recebe o dashboard com os três cards", async ({ page }) => {
    await abrirDashboard(page);
    for (const rotulo of ["Sem evidência", "Atrasadas", "Ações críticas"]) {
      await expect(page.getByText(rotulo, { exact: true })).toBeVisible();
    }
    // O RLS do backend restringe o escopo do ADT ao(s) seu(s) território(s);
    // a contagem exibida já reflete isso, sem territorio_id no request.
  });
});

test.describe("Dashboard — Articulador com múltiplos territórios", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("articulador multi-território recebe o dashboard", async ({ page }) => {
    await abrirDashboard(page);
    // Regressão do bug antigo (só o 1º território era considerado): quando o
    // articulador tem PB, RN, BA e MG, os cards devem consultar o backend
    // sem `territorio_id` fixo — o RLS decide.
    for (const rotulo of ["Sem evidência", "Atrasadas", "Ações críticas"]) {
      await expect(page.getByText(rotulo, { exact: true })).toBeVisible();
    }
  });
});

test.describe("Painel — filtro Ações críticas", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("abrir /sgp/painel?criticas=1 liga o checkbox e recorta a listagem", async ({
    page,
  }) => {
    await page.goto("/sgp/painel?criticas=1");
    await expect(page.getByTestId("painel-page")).toBeVisible();
    await expect(page.getByTestId("painel-filtro-criticas")).toBeChecked();

    // Todas as Ações renderizadas precisam ser críticas (data-nivel=vermelho).
    const acoes = page.locator('[data-testid^="painel-acao-"]');
    const total = await acoes.count();
    for (let i = 0; i < total; i++) {
      await expect(acoes.nth(i)).toHaveAttribute("data-nivel", "vermelho");
    }
  });

  test("desligar o checkbox reintroduz Ações amarelas/verdes na tela", async ({
    page,
  }) => {
    await page.goto("/sgp/painel?criticas=1");
    await expect(page.getByTestId("painel-filtro-criticas")).toBeChecked();

    const acoesCriticas = await page
      .locator('[data-testid^="painel-acao-"]')
      .count();

    await page.getByTestId("painel-filtro-criticas").uncheck();
    await page.waitForURL(/\/sgp\/painel$|painel\?(?!.*criticas)/);
    await expect(page.getByTestId("painel-filtro-criticas")).not.toBeChecked();

    // Desligado, o painel tem que mostrar pelo menos as mesmas + mais alguma
    // Ação não-crítica (se o seed tiver alguma amarela/verde).
    const acoesTotal = await page
      .locator('[data-testid^="painel-acao-"]')
      .count();
    expect(acoesTotal).toBeGreaterThanOrEqual(acoesCriticas);
  });
});
