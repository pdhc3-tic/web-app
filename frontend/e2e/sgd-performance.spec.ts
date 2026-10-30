import { expect, test, type Page } from "@playwright/test";
import {
  VOLUME_DEMANDAS,
  criarVolumeDemandasFixture,
  removerVolumeDemandasFixture,
} from "./helpers/volumeDemandasFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Performance e carregamento do SGD (#323 · SGD-FE-12), contra o backend real.
 *
 * 1. Skeleton na mesma grade da tabela enquanto o painel por rubrica e a
 *    listagem de demandas carregam. Só aqui o `page.route` entra, e só para
 *    atrasar a resposta real: o conteúdo continua vindo do backend.
 * 2. Cache do TanStack Query (#271): voltar a uma aba recém-visitada não refaz
 *    a mesma requisição dentro do `staleTime`.
 * 3. Debounce do filtro de atividade: uma busca por texto estável, não uma por
 *    tecla (o teste de componente fica em `SearchSelect.test.tsx`).
 * 4. Volume alto: 10.000 demandas sintéticas, navegadas pela paginação real
 *    do `DemandPagination`.
 */

test.describe.configure({ mode: "serial" });

const PAINEL_RUBRICAS = "/api/v1/sgd/painel/rubricas/";

/** Teto por troca de página: acima disso o usuário percebe travamento. */
const TETO_TROCA_DE_PAGINA_MS = 3_000;

test.describe("SGD — carregamento sem salto de layout (#323)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("painel por rubrica mostra o skeleton antes dos dados reais", async ({ page }) => {
    await page.route(`**${PAINEL_RUBRICAS}*`, async (route) => {
      await new Promise((r) => setTimeout(r, 300));
      await route.continue();
    });

    await page.goto("/sgd/execucao");
    const skeleton = page.getByTestId("painel-rubricas-skeleton");
    await expect(skeleton).toBeVisible();
    await expect(skeleton).toBeHidden({ timeout: 10_000 });
  });

  test("listagem de demandas mostra o skeleton antes da tabela real", async ({ page }) => {
    await page.route("**/api/v1/sgd/demandas/?*", async (route) => {
      await new Promise((r) => setTimeout(r, 300));
      await route.continue();
    });

    await page.goto("/sgd/demandas?visao=todas");
    const skeleton = page.getByTestId("demandas-skeleton");
    await expect(skeleton).toBeVisible();
    await expect(skeleton).toBeHidden({ timeout: 10_000 });
    await expect(page.getByTestId("demandas-tabela")).toBeVisible();
  });

  test("voltar à aba do painel não refaz a mesma requisição dentro do staleTime", async ({ page }) => {
    const chamadas: string[] = [];
    page.on("request", (r) => {
      if (new URL(r.url()).pathname === PAINEL_RUBRICAS) chamadas.push(r.url());
    });

    const primeira = page.waitForResponse((r) => new URL(r.url()).pathname === PAINEL_RUBRICAS);
    await page.goto("/sgd/execucao");
    await primeira;
    await expect(page.getByTestId("tab-rubricas")).toHaveAttribute("aria-selected", "true");
    const depoisDaPrimeiraCarga = chamadas.length;
    expect(depoisDaPrimeiraCarga).toBeGreaterThan(0);

    await page.getByTestId("tab-custo-atividades").click();
    await expect(page.getByTestId("tab-custo-atividades")).toHaveAttribute("aria-selected", "true");
    await page.getByTestId("tab-rubricas").click();
    await expect(page.getByTestId("tab-rubricas")).toHaveAttribute("aria-selected", "true");
    await page.waitForTimeout(500);

    expect(chamadas).toHaveLength(depoisDaPrimeiraCarga);
  });

  test("filtro de atividade: uma busca por texto estável, não uma por tecla", async ({ page }) => {
    const buscas: string[] = [];
    page.on("request", (r) => {
      const url = new URL(r.url());
      if (url.pathname === "/api/v1/sgp/atividades/" && url.searchParams.has("q")) {
        buscas.push(url.searchParams.get("q")!);
      }
    });

    await page.goto("/sgd/execucao");
    const campo = page.getByTestId("filtro-atividade");
    await campo.click();
    const resposta = page.waitForResponse((r) => new URL(r.url()).searchParams.get("q") === "ativ");
    await campo.pressSequentially("ativ", { delay: 50 });
    await resposta;
    await page.waitForTimeout(500);

    expect(buscas).toEqual(["ativ"]);
  });
});

test.describe("SGD — listagem de demandas com volume alto (#323)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.beforeAll(() => {
    const fx = criarVolumeDemandasFixture();
    expect(fx.criadas).toBe(VOLUME_DEMANDAS);
  });

  test.afterAll(() => {
    removerVolumeDemandasFixture();
  });

  /** O resumo do `Pagination`: "1–50 de 10011 demandas". */
  function resumo(page: Page) {
    return page.getByTestId("demandas-lista").getByText(/^\d+–\d+ de \d+/);
  }

  /** O resumo como números: a faixa da página e o total. */
  async function faixa(page: Page) {
    const texto = (await resumo(page).textContent()) ?? "";
    const [, de, ate, total] = texto.replace(/\./g, "").match(/(\d+)–(\d+) de (\d+)/) ?? [];
    return { de: Number(de), ate: Number(ate), total: Number(total) };
  }

  async function trocarDePagina(page: Page, botao: string, faixaEsperada: RegExp) {
    const inicio = Date.now();
    await page.getByRole("button", { name: botao }).click();
    // A página anterior fica na tela enquanto a próxima carrega: nada de skeleton.
    await expect(page.getByTestId("demandas-skeleton")).toHaveCount(0);
    await expect(resumo(page)).toHaveText(faixaEsperada);
    await expect(page.getByTestId("demandas-lista")).toHaveAttribute("aria-busy", "false");
    return Date.now() - inicio;
  }

  test("navega pelas páginas de 10.000+ demandas sem travar e sem voltar ao skeleton", async ({ page }) => {
    const inicio = Date.now();
    await page.goto("/sgd/demandas?visao=todas");
    await expect(page.getByTestId("demandas-tabela")).toBeVisible({ timeout: 15_000 });
    test.info().annotations.push({ type: "primeira carga (ms)", description: String(Date.now() - inicio) });

    const primeira = await faixa(page);
    expect(primeira).toMatchObject({ de: 1, ate: 50 });
    expect(primeira.total).toBeGreaterThanOrEqual(VOLUME_DEMANDAS);
    await expect(page.locator('tr[data-testid^="demanda-linha-"]')).toHaveCount(50);

    const tempos = [
      await trocarDePagina(page, "Próxima página", /51–100 de/),
      await trocarDePagina(page, "Próxima página", /101–150 de/),
      await trocarDePagina(page, "Página anterior", /51–100 de/),
    ];
    await expect(page).toHaveURL(/offset=50/);

    const ultimaPagina = Math.floor((primeira.total - 1) / 50) * 50;
    tempos.push(
      await trocarDePagina(page, "Última página", new RegExp(`${ultimaPagina + 1}–[\\d.]+ de`)),
    );
    const ultima = await faixa(page);
    expect(ultima.ate).toBe(primeira.total);
    await expect(page.locator('tr[data-testid^="demanda-linha-"]')).toHaveCount(ultima.ate - ultima.de + 1);

    tempos.push(await trocarDePagina(page, "Primeira página", /^1–50 de/));
    test.info().annotations.push({ type: "trocas de página (ms)", description: tempos.join(", ") });
    for (const ms of tempos) expect(ms).toBeLessThan(TETO_TROCA_DE_PAGINA_MS);
  });

  test("a página fica na URL: abrir o link direto cai na mesma faixa", async ({ page }) => {
    await page.goto("/sgd/demandas?visao=todas&offset=5000");
    await expect(page.getByTestId("demandas-tabela")).toBeVisible({ timeout: 15_000 });
    expect(await faixa(page)).toMatchObject({ de: 5001, ate: 5050 });
  });

  test("uma página além do fim volta para a última que existe", async ({ page }) => {
    await page.goto("/sgd/demandas?visao=todas&offset=999950");
    await expect(page).not.toHaveURL(/offset=999950/);
    await expect(page.getByTestId("demandas-tabela")).toBeVisible({ timeout: 15_000 });
    const ultima = await faixa(page);
    expect(ultima.ate).toBe(ultima.total);
    await expect(page).toHaveURL(new RegExp(`offset=${ultima.de - 1}`));
  });
});
