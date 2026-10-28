import { expect, test, type Page } from "@playwright/test";
import { criarAtividadeAtrasada, removerAtividadeAtrasada } from "./helpers/atrasadaFixture";
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
    // O filtro `atrasada` já existe em `backend/apps/sgp/filters.py`
    // (StrictBooleanFilter), implementado antes do PR da #236.
    await expect(link).toHaveAttribute(
      "href",
      /\/sgp\/atividades\?atrasada=true/,
    );
  });

  test.describe("A1 da #302: card Atrasadas contra a listagem real", () => {
    test.beforeAll(() => {
      criarAtividadeAtrasada();
    });

    test.afterAll(() => {
      removerAtividadeAtrasada();
    });

    test("a contagem do card é o total da listagem /sgp/atividades?atrasada=true", async ({ page }) => {
      // A fixture garante ao menos uma atrasada: o card mostra um número, não
      // "Nenhuma pendência", e a comparação nunca é trivial.
      const contagem = page.waitForResponse((r) => {
        const url = new URL(r.url());
        return url.pathname === "/api/v1/sgp/atividades/" && url.searchParams.get("atrasada") === "true";
      });
      await abrirDashboard(page);
      const api = new URL((await contagem).url()).origin;
      const numeroDoCard = card(page, 1).locator("span.tabular-nums");
      await expect(numeroDoCard).toHaveText(/^\d+$/);
      const doCard = Number(await numeroDoCard.textContent());
      expect(doCard).toBeGreaterThan(0);

      // A mesma consulta direto na API, com o token da sessão (Bearer).
      const daApi = await page.evaluate(async (api) => {
        const sessao = await (await fetch("/api/auth/session")).json();
        const res = await fetch(`${api}/api/v1/sgp/atividades/?atrasada=true&page_size=1`, {
          headers: { Authorization: `Bearer ${sessao.accessToken}` },
        });
        if (!res.ok) throw new Error(`listagem respondeu ${res.status}`);
        return ((await res.json()) as { count: number }).count;
      }, api);
      expect(daApi).toBe(doCard);

      // E a listagem que o link do card abre mostra o mesmo total.
      await card(page, 1).getByRole("link", { name: /Ver listagem/ }).click();
      await expect(page).toHaveURL(/\/sgp\/atividades\?atrasada=true/);
      await expect(page.getByText(new RegExp(`^\\d+–\\d+ de ${doCard} atividades?$`))).toBeVisible();
    });
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
    // O seed tem Ações críticas: o card mostra um número, e a comparação vale.
    const cardCriticas = card(page, 2);
    const numero = cardCriticas.locator("span.tabular-nums").first();
    await expect(numero).toHaveText(/^\d+$/);
    const esperado = Number(await numero.textContent());
    expect(esperado).toBeGreaterThan(0);

    // Vai para o painel com o filtro do card.
    await cardCriticas
      .getByRole("link", { name: /Ver listagem/ })
      .click();
    await page.waitForURL(/criticas=1/);

    // Espera o painel resolver: cada Ação renderiza um data-testid próprio.
    // O total contado pelo painel após o filtro tem que casar com o card.
    await expect(page.getByTestId("painel-page")).toBeVisible();
    const acoesNoPainel = page.locator('[data-testid^="painel-acao-"]');
    await expect(acoesNoPainel.first()).toBeVisible();
    // Uma Ação pode aparecer mais de uma vez (alerta + card da Meta): conta os
    // ids distintos, esperando o painel terminar de montar os grupos.
    await expect
      .poll(async () => new Set(await acoesNoPainel.evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")))).size)
      .toBe(esperado);
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

    // Ligado, só ficam as Metas com alguma Ação vermelha. As linhas de cada
    // Meta só aparecem com ela expandida, então a conta é por Meta.
    const metas = page.locator('[data-testid^="painel-meta-"]:not([data-testid*="toggle"])');
    await expect(metas.first()).toBeVisible();
    const metasComCriticas = await metas.count();

    // O checkbox é controlado pela URL: o estado só muda depois da navegação,
    // então clica e espera a URL e o estado, em vez de `uncheck()`.
    await page.getByTestId("painel-filtro-criticas").click();
    await page.waitForURL(/\/sgp\/painel$|painel\?(?!.*criticas)/);
    await expect(page.getByTestId("painel-filtro-criticas")).not.toBeChecked();

    // Desligado, voltam as Metas só com Ações amarelas ou verdes do seed.
    await expect.poll(() => metas.count()).toBeGreaterThan(metasComCriticas);
  });
});
