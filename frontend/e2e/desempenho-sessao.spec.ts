import { expect, test, type Page } from "@playwright/test";
import { primeiroUfpaId } from "./helpers/ufpa";
import { storageStatePath } from "./helpers/users";

/**
 * #448 — Sessão lida uma vez e estados de carregamento corretos, contra o
 * backend real. `page.route` só atrasa ou derruba requisições, como manda a
 * regra das specs: a resposta é sempre a do backend.
 *
 * O prefetch só existe no build de produção, então não é medido aqui; os
 * números de antes e depois estão no comentário de entrega da issue.
 */

const SESSAO = "/api/auth/session";

/** Conta as idas a `/api/auth/session` a partir de agora. */
function contarSessao(page: Page) {
  const contador = { total: 0 };
  page.on("request", (r) => {
    if (new URL(r.url()).pathname === SESSAO) contador.total++;
  });
  return contador;
}

/** Atrasa as respostas da rota, sem mudar o conteúdo. */
async function atrasar(page: Page, padrao: RegExp, ms: number) {
  await page.route(padrao, async (route) => {
    await new Promise((r) => setTimeout(r, ms));
    await route.continue();
  });
}

test.describe("Sessão (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("abrir uma lista e navegar pelo menu não relê a sessão a cada chamada da API", async ({ page }) => {
    const sessao = contarSessao(page);
    const api: string[] = [];
    page.on("request", (r) => {
      if (new URL(r.url()).pathname.startsWith("/api/v1/")) api.push(r.url());
    });

    await page.goto("/sgp/ufpas");
    await expect(page.locator("tbody tr[tabindex='0']").first()).toBeVisible();
    expect(api.length, "a tela chama a API várias vezes").toBeGreaterThan(2);
    expect(sessao.total, "carga direta").toBeLessThanOrEqual(1);

    for (const [link, url] of [
      ["SGD", /\/sgd$/],
      ["SGP", /\/sgp$/],
      ["Core", /\/core$/],
    ] as const) {
      sessao.total = 0;
      await page.getByRole("navigation", { name: "Navegação principal", exact: true }).getByRole("link", { name: link, exact: true }).click();
      await expect(page).toHaveURL(url);
      await page.waitForTimeout(1500);
      expect(sessao.total, `navegação até ${link}`).toBeLessThanOrEqual(1);
    }
  });

  test("o menu já vem completo do servidor, mesmo sem /api/auth/session", async ({ page }) => {
    // Derrubar a rota prova que o menu não depende dela para montar.
    await page.route(new RegExp(`${SESSAO}$`), (route) => route.abort());
    await page.goto("/sgp");
    await expect(page.getByText("Beatriz Nogueira")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sair", exact: true })).toBeVisible();
  });

  test("a sessão guarda só o necessário: perfis enxutos e sem a lista de territórios do perfil nacional", async ({
    page,
  }) => {
    await page.goto("/sgp");
    const sessao = (await (await page.request.get(SESSAO)).json()) as {
      user: { perfis: Record<string, unknown>[]; territorios: unknown[] };
    };
    expect(sessao.user.perfis.length).toBeGreaterThan(0);
    for (const p of sessao.user.perfis) {
      expect(Object.keys(p).sort()).toEqual(expect.arrayContaining(["id", "nome", "slug"]));
      expect(p).not.toHaveProperty("descricao");
    }
    expect(sessao.user.territorios).toEqual([]);
  });
});

test.describe("Sessão (Super Admin)", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("o bloco administrativo do menu aparece sem esperar a sessão do cliente", async ({ page }) => {
    await page.route(new RegExp(`${SESSAO}$`), (route) => route.abort());
    await page.goto("/dashboard");
    // "Usuários" é do bloco administrativo, que antes só aparecia depois da sessão chegar ao cliente.
    await expect(page.getByRole("navigation", { name: "Navegação principal", exact: true }).getByRole("link", { name: "Usuários", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sair", exact: true })).toBeVisible();
  });
});

test.describe("Carregamento (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a listagem de UFPAs diz \"Carregando…\" em vez de \"0–0 de 0\"", async ({ page }) => {
    await atrasar(page, /\/api\/v1\/sgp\/ufpas\/\?/, 1500);
    const resposta = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/sgp/ufpas/");
    await page.goto("/sgp/ufpas");
    await expect(page.getByTestId("paginacao-carregando")).toHaveText("Carregando UFPAs…");
    await expect(page.getByText(/0–0 de 0/)).toHaveCount(0);

    const { count } = (await (await resposta).json()) as { count: number };
    await expect(page.getByTestId("paginacao-carregando")).toHaveCount(0);
    await expect(page.getByText(new RegExp(`de ${count} UFPAs?$`))).toBeVisible();
  });
});

// Editar UFPA é escrita: a UGP não abre o wizard (#478).
test.describe("Carregamento (Super Admin)", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("Editar UFPA: localização travada com \"Carregando…\" e Avançar desabilitado até as opções chegarem", async ({
    page,
  }) => {
    await atrasar(page, /\/api\/v1\/(municipalities|municipios)\//, 2000);
    await page.goto(`/sgp/ufpas/${primeiroUfpaId()}/editar`);

    const municipio = page.getByRole("combobox", { name: /^Município/ });
    await expect(municipio).toHaveText(/Carregando…/);
    await expect(municipio).toBeDisabled();
    await expect(page.getByTestId("ufpa-wizard-avancar")).toBeDisabled();

    await expect(municipio).not.toHaveText(/Carregando|Selecione|Escolha/, { timeout: 15_000 });
    await expect(municipio).toBeEnabled();
    await expect(page.getByTestId("ufpa-wizard-avancar")).toBeEnabled();
  });
});
