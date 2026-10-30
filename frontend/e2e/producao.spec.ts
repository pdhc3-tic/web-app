import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Produção da UPF consolidada (#238, A3 da #302) contra o backend real e o
 * `seed_demo` (69 produções, 23 culturas). Cada teste compara a tela com a
 * própria API, consultada com o token da sessão.
 *
 * Só a falha do servidor é forçada (500), porque o backend real não falha sob
 * encomenda. O estado vazio sem filtros não tem como existir com o seed, então
 * não é testado aqui.
 */

type Paginado<T> = { count: number; results: T[] };
type ItemProducao = { id: number; upf_id: number; upf_nome_titular: string; tipo: string; cultura: { id: number; nome: string } | null };
type Indicadores = { total_upfs_produtoras: number; area_total_ha: string | null; principais_culturas: { nome: string }[] };
type ItemCatalogo = { id: number; nome: string };

/** Abre a tela e devolve a origem da API, lida de uma requisição real dela. */
async function abrir(page: Page, query = ""): Promise<string> {
  const indicadores = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/sgp/producao/indicadores/");
  await page.goto(`/sgp/producao${query}`);
  return new URL((await indicadores).url()).origin;
}

/** GET autenticado direto na API, com o mesmo token da sessão da tela. */
async function api<T>(page: Page, origem: string, caminho: string): Promise<T> {
  return page.evaluate(
    async ({ url }) => {
      const sessao = await (await fetch("/api/auth/session")).json();
      const res = await fetch(url, { headers: { Authorization: `Bearer ${sessao.accessToken}` } });
      if (!res.ok) throw new Error(`${url} respondeu ${res.status}`);
      return res.json();
    },
    { url: `${origem}${caminho}` },
  ) as Promise<T>;
}

test.describe("SGP — Produção da UPF consolidada", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("card Produção aparece na página do SGP com link funcional", async ({ page }) => {
    await page.goto("/sgp");
    const card = page.getByRole("link", { name: /Produção da UPF/i });
    await expect(card).toBeVisible();
    expect(await card.getAttribute("href")).toContain("/sgp/producao");
  });

  test("lista e indicadores batem com a API, e o titular leva à aba Produção da UPF", async ({ page }) => {
    const origem = await abrir(page);
    const [lista, indicadores] = await Promise.all([
      api<Paginado<ItemProducao>>(page, origem, "/api/v1/sgp/producao/?page=1&page_size=20"),
      api<Indicadores>(page, origem, "/api/v1/sgp/producao/indicadores/"),
    ]);
    expect(lista.count).toBeGreaterThan(0);

    await expect(page.getByTestId("producao-indicador-upfs")).toHaveText(String(indicadores.total_upfs_produtoras));
    await expect(page.getByRole("columnheader", { name: "UPF / Titular" })).toBeVisible();

    const primeiro = lista.results[0];
    const linha = page.getByTestId(`producao-linha-${primeiro.id}`);
    await expect(linha).toContainText(primeiro.upf_nome_titular);
    await expect(linha.getByRole("link", { name: primeiro.upf_nome_titular })).toHaveAttribute(
      "href",
      `/sgp/upfs/${primeiro.upf_id}?tab=producao`,
    );
  });

  test("tipo e cultura filtram a lista e os indicadores (A3 da #302)", async ({ page }) => {
    const origem = await abrir(page);
    const todas = await api<Paginado<ItemProducao>>(page, origem, "/api/v1/sgp/producao/?page=1&page_size=200");
    const comCultura = todas.results.find((p) => p.tipo === "agricola" && p.cultura)!;
    const cultura = comCultura.cultura!;
    const filtro = `tipo=agricola&cultura=${cultura.id}`;

    // A tela pede os indicadores com os mesmos filtros da listagem.
    const pedidoIndicadores = page.waitForRequest((r) => {
      const url = new URL(r.url());
      return (
        url.pathname === "/api/v1/sgp/producao/indicadores/" &&
        url.searchParams.get("tipo") === "agricola" &&
        url.searchParams.get("cultura") === String(cultura.id)
      );
    });
    await page.goto(`/sgp/producao?${filtro}`);
    await pedidoIndicadores;

    const [lista, indicadores, semFiltro] = await Promise.all([
      api<Paginado<ItemProducao>>(page, origem, `/api/v1/sgp/producao/?page=1&page_size=200&${filtro}`),
      api<Indicadores>(page, origem, `/api/v1/sgp/producao/indicadores/?${filtro}`),
      api<Indicadores>(page, origem, "/api/v1/sgp/producao/indicadores/"),
    ]);
    // O recorte muda de fato os indicadores: não é o total geral repetido.
    expect(indicadores.total_upfs_produtoras).toBeLessThan(semFiltro.total_upfs_produtoras);
    await expect(page.getByTestId("producao-indicador-upfs")).toHaveText(String(indicadores.total_upfs_produtoras));
    expect(indicadores.principais_culturas.map((c) => c.nome)).toEqual([cultura.nome]);

    // A listagem mostra exatamente as produções do recorte.
    await expect(page.locator('tr[data-testid^="producao-linha-"]')).toHaveCount(lista.results.length);
    for (const item of lista.results) {
      await expect(page.getByTestId(`producao-linha-${item.id}`)).toContainText(cultura.nome);
    }
  });

  test("filtro sem resultado mostra o estado vazio e 'Limpar filtros'", async ({ page }) => {
    const origem = await abrir(page);
    const culturas = await api<Paginado<ItemCatalogo>>(page, origem, "/api/v1/catalogos/culturas/?page_size=1");
    // Pecuária nunca tem cultura: o recorte é vazio de verdade no backend.
    const filtro = `tipo=pecuaria&cultura=${culturas.results[0].id}`;
    const vazia = await api<Paginado<ItemProducao>>(page, origem, `/api/v1/sgp/producao/?page=1&page_size=20&${filtro}`);
    expect(vazia.count).toBe(0);

    await page.goto(`/sgp/producao?${filtro}`);
    await expect(page.getByText("Nenhum registro encontrado")).toBeVisible();
    await page.getByRole("button", { name: "Limpar filtros" }).click();
    await expect(page.locator('tr[data-testid^="producao-linha-"]').first()).toBeVisible();
  });

  test("restaura cultura e espécie da URL, mesmo com o id fora da primeira página do catálogo", async ({ page }) => {
    const origem = await abrir(page);
    const [culturas, especies] = await Promise.all([
      api<Paginado<ItemCatalogo>>(page, origem, "/api/v1/catalogos/culturas/?page_size=200"),
      api<Paginado<ItemCatalogo>>(page, origem, "/api/v1/catalogos/especies-animais/?page_size=200"),
    ]);
    // O último do catálogo: com mais de 50 culturas, fica além da página padrão.
    const cultura = culturas.results[culturas.results.length - 1];
    const especie = especies.results[especies.results.length - 1];

    await page.goto(`/sgp/producao?cultura=${cultura.id}&especie=${especie.id}`);
    await expect(page.getByText(cultura.nome, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(especie.nome, { exact: true }).first()).toBeVisible();
  });

  test("erro do servidor exibe mensagem e botão Tentar novamente", async ({ page }) => {
    // Falha forçada: o único caso em que a resposta é interceptada.
    await page.route("**/api/v1/sgp/producao/**", (route) =>
      route.request().method() === "GET" ? route.fulfill({ status: 500, body: "error" }) : route.fallback(),
    );
    await page.goto("/sgp/producao");
    await expect(page.getByText(/Não foi possível carregar/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar novamente" }).first()).toBeVisible();
  });
});
