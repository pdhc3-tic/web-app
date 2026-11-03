import { expect, test, type Page } from "@playwright/test";
import {
  criarOrdenacaoFixture,
  removerOrdenacaoFixture,
  type OrdenacaoFixture,
} from "./helpers/ordenacaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #364 — a coluna "Valor estimado" ordena pelo servidor (`?ordering=`), e o
 * estado da ordenação fica na URL.
 *
 * Contra o backend real: a fixture cria três demandas do ADT com valores
 * diferentes, e a spec confere a ordem que a API devolve. A lista é
 * filtrada pela atividade da fixture (recorte do #297), para não depender do
 * que outras specs deixam no banco. As requisições são só observadas, nunca
 * respondidas pelo teste.
 */

test.describe.configure({ mode: "serial" });

let fx: OrdenacaoFixture;
/** Ids na ordem de criação: valores 1800, 500, 3200. */
let ida: number, apoio: number, comitiva: number;

test.beforeAll(() => {
  fx = criarOrdenacaoFixture();
  [ida, apoio, comitiva] = fx.demandas.map((d) => d.id);
});

test.afterAll(() => {
  removerOrdenacaoFixture();
});

/** Guarda o `ordering` de cada GET da listagem que o front fizer. */
function observarOrdering(page: Page): (string | null)[] {
  const orderings: (string | null)[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (req.method() === "GET" && url.pathname.endsWith("/api/v1/sgd/demandas/")) {
      orderings.push(url.searchParams.get("ordering"));
    }
  });
  return orderings;
}

async function idsNaOrdem(page: Page): Promise<number[]> {
  const testids = await page
    .getByTestId("demandas-tabela")
    .locator("tbody tr[data-testid^='demanda-linha-']")
    .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid") ?? ""));
  return testids.map((t) => Number(t.replace("demanda-linha-", "")));
}

const coluna = (page: Page) =>
  page.getByTestId("demandas-tabela").getByRole("columnheader", { name: /Valor/ });
const ordenarPorValor = (page: Page) => page.getByTestId("demandas-ordenar-valor");
const lista = () => `/sgd/demandas?atividade=${fx.atividadeId}`;

test.describe("ADT — ordenação por valor (#364)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o ciclo asc → desc → padrão fica na URL e a ordem vem do servidor", async ({ page }) => {
    const orderings = observarOrdering(page);
    await page.goto(lista());

    // Padrão do backend (`-criado_em`): a última criada primeiro.
    await expect.poll(() => idsNaOrdem(page)).toEqual([comitiva, apoio, ida]);
    await expect(coluna(page)).toHaveAttribute("aria-sort", "none");
    expect(orderings.at(-1)).toBeNull();

    await ordenarPorValor(page).click();
    await expect(page).toHaveURL(/[?&]ordering=valor_estimado_total/);
    await expect(coluna(page)).toHaveAttribute("aria-sort", "ascending");
    await expect.poll(() => idsNaOrdem(page)).toEqual([apoio, ida, comitiva]);
    expect(orderings.at(-1)).toBe("valor_estimado_total");

    await ordenarPorValor(page).click();
    await expect(page).toHaveURL(/[?&]ordering=-valor_estimado_total/);
    await expect(coluna(page)).toHaveAttribute("aria-sort", "descending");
    await expect.poll(() => idsNaOrdem(page)).toEqual([comitiva, ida, apoio]);
    expect(orderings.at(-1)).toBe("-valor_estimado_total");

    // Terceiro clique: o `ordering` sai da URL e volta a ordem padrão.
    await ordenarPorValor(page).click();
    await expect(page).not.toHaveURL(/ordering=/);
    await expect(coluna(page)).toHaveAttribute("aria-sort", "none");
    await expect.poll(() => idsNaOrdem(page)).toEqual([comitiva, apoio, ida]);
    // O recorte da atividade continua aplicado durante todo o ciclo.
    await expect(page).toHaveURL(new RegExp(`atividade=${fx.atividadeId}`));
  });

  test("deep link com `ordering` reconstrói a visão", async ({ page }) => {
    await page.goto(`${lista()}&ordering=-valor_estimado_total`);
    await expect(coluna(page)).toHaveAttribute("aria-sort", "descending");
    await expect.poll(() => idsNaOrdem(page)).toEqual([comitiva, ida, apoio]);
  });

  test("`ordering` inválido na URL é ignorado e a lista entra na ordem padrão", async ({ page }) => {
    const orderings = observarOrdering(page);
    await page.goto(`${lista()}&ordering=qualquer-coisa`);
    await expect(coluna(page)).toHaveAttribute("aria-sort", "none");
    await expect.poll(() => idsNaOrdem(page)).toEqual([comitiva, apoio, ida]);
    expect(orderings).not.toContain("qualquer-coisa");
  });
});
