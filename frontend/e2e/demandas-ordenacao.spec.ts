import { expect, test, type Page, type Route } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #364 — a coluna "Valor estimado" ordena pelo servidor (`?ordering=`), e o
 * estado da ordenação fica na URL.
 *
 * A ordem produzida pelo backend já é coberta em
 * `backend/apps/sgd/tests/test_demand_totais.py`. Aqui o foco é o front: o
 * clique dispara a requisição com o `ordering` certo, o cabeçalho reflete a
 * direção em `aria-sort`, e o deep link reconstrói a mesma visão.
 */

test.describe.configure({ mode: "serial" });

type DemandaSimulada = {
  id: number;
  titulo: string;
  valor_estimado_total: string;
};

const DEMANDAS: DemandaSimulada[] = [
  { id: 701, titulo: "Van da oficina", valor_estimado_total: "500.00" },
  { id: 702, titulo: "Combustível do deslocamento", valor_estimado_total: "1800.00" },
  { id: 703, titulo: "Diárias da equipe", valor_estimado_total: "3200.00" },
];

/** Serializa uma demanda com o mínimo que a listagem (#296) usa. */
function serializar(d: DemandaSimulada) {
  return {
    id: d.id,
    titulo: d.titulo,
    activity: 1,
    justificativa: "",
    status: "submetida",
    status_display: "Submetida",
    transicoes_permitidas: [],
    solicitante: 1,
    solicitante_nome: "ADT",
    despesa_posterior: false,
    valor_estimado_total: d.valor_estimado_total,
    valor_autorizado_total: "0.00",
    valor_pago_total: "0.00",
    contexto: {
      territorio_id: 1,
      territorio_nome: "RN",
      municipio_id: 1,
      municipio_nome: "Natal",
      comunidade_id: null,
      comunidade_nome: null,
      data_prevista: "2026-11-10T08:00:00-03:00",
      tecnico_id: 1,
      tecnico_nome: "ADT",
      acao_numero: "1.1",
      acao_descricao: "Ação",
      meta_numero: 1,
      meta_titulo: "Meta 1",
    },
    solicitacoes: [],
    etapas: [],
    criado_em: "2026-11-01T00:00:00-03:00",
    atualizado_em: "2026-11-01T00:00:00-03:00",
  };
}

/** Ordena a lista simulada conforme o `ordering` que o front mandar. */
function ordenar(ordering: string | null): DemandaSimulada[] {
  if (ordering === "valor_estimado_total") {
    return [...DEMANDAS].sort(
      (a, b) => Number(a.valor_estimado_total) - Number(b.valor_estimado_total),
    );
  }
  if (ordering === "-valor_estimado_total") {
    return [...DEMANDAS].sort(
      (a, b) => Number(b.valor_estimado_total) - Number(a.valor_estimado_total),
    );
  }
  return DEMANDAS;
}

/** Captura o `ordering` enviado ao backend em cada requisição da listagem. */
async function montarMock(page: Page): Promise<{ orderings: (string | null)[] }> {
  const orderings: (string | null)[] = [];
  await page.route("**/api/v1/sgd/demandas/?*", async (route: Route) => {
    const url = new URL(route.request().url());
    const ordering = url.searchParams.get("ordering");
    orderings.push(ordering);
    const lista = ordenar(ordering);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        count: lista.length,
        next: null,
        previous: null,
        results: lista.map(serializar),
      }),
    });
  });
  return { orderings };
}

async function idsNaOrdem(page: Page): Promise<number[]> {
  const linhas = await page
    .getByTestId("demandas-tabela")
    .locator("tbody tr[data-testid^='demanda-linha-']")
    .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid") ?? ""));
  return linhas.map((t) => Number(t.replace("demanda-linha-", "")));
}

const cabecalhoValor = (page: Page) => page.getByTestId("demandas-ordenar-valor");

test.describe("Articulador PB — ordenação por valor (#364)", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("o ciclo asc → desc → sem ordenação persiste na URL e dispara a requisição", async ({
    page,
  }) => {
    const { orderings } = await montarMock(page);

    await page.goto("/sgd/demandas?visao=todas");
    await expect(page.getByTestId("demandas-tabela")).toBeVisible();
    // Sem ordenação, a lista entra na ordem padrão (sem `ordering` no servidor).
    expect(orderings.at(-1)).toBeNull();
    expect(await idsNaOrdem(page)).toEqual([701, 702, 703]);
    const coluna = page.getByTestId("demandas-tabela").getByRole("columnheader", { name: /Valor/ });
    await expect(coluna).toHaveAttribute("aria-sort", "none");

    // Primeiro clique: ascendente. URL e requisição refletem o novo estado.
    await cabecalhoValor(page).click();
    await expect(page).toHaveURL(/ordering=valor_estimado_total(?!-)/);
    await expect(coluna).toHaveAttribute("aria-sort", "ascending");
    await expect
      .poll(() => orderings.at(-1), { timeout: 5_000 })
      .toBe("valor_estimado_total");
    expect(await idsNaOrdem(page)).toEqual([701, 702, 703]);

    // Segundo clique: descendente.
    await cabecalhoValor(page).click();
    await expect(page).toHaveURL(/ordering=-valor_estimado_total/);
    await expect(coluna).toHaveAttribute("aria-sort", "descending");
    await expect
      .poll(() => orderings.at(-1), { timeout: 5_000 })
      .toBe("-valor_estimado_total");
    expect(await idsNaOrdem(page)).toEqual([703, 702, 701]);

    // Terceiro clique: volta ao padrão do backend; o `ordering` sai da URL.
    await cabecalhoValor(page).click();
    await expect(page).not.toHaveURL(/ordering=/);
    await expect(coluna).toHaveAttribute("aria-sort", "none");
    await expect
      .poll(() => orderings.at(-1), { timeout: 5_000 })
      .toBeNull();
  });

  test("deep link com `ordering` reconstrói a visão", async ({ page }) => {
    const { orderings } = await montarMock(page);

    await page.goto("/sgd/demandas?visao=todas&ordering=-valor_estimado_total");
    await expect(page.getByTestId("demandas-tabela")).toBeVisible();
    const coluna = page.getByTestId("demandas-tabela").getByRole("columnheader", { name: /Valor/ });
    await expect(coluna).toHaveAttribute("aria-sort", "descending");
    await expect
      .poll(() => orderings.at(-1), { timeout: 5_000 })
      .toBe("-valor_estimado_total");
    expect(await idsNaOrdem(page)).toEqual([703, 702, 701]);
  });

  test("`ordering` inválido na URL é ignorado e a lista entra sem ordenação", async ({ page }) => {
    const { orderings } = await montarMock(page);

    await page.goto("/sgd/demandas?visao=todas&ordering=qualquer-coisa");
    await expect(page.getByTestId("demandas-tabela")).toBeVisible();
    const coluna = page.getByTestId("demandas-tabela").getByRole("columnheader", { name: /Valor/ });
    await expect(coluna).toHaveAttribute("aria-sort", "none");
    expect(orderings.at(-1)).toBeNull();
  });
});
