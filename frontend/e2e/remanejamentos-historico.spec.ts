import { expect, test, type Page, type Response } from "@playwright/test";
import {
  criarHistoricoRemanejamentosFixture,
  removerHistoricoRemanejamentosFixture,
  type HistoricoRemanejamentosFixture,
} from "./helpers/historicoRemanejamentosFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #466 (SGP-RF41) — Histórico de remanejamentos, contra o backend real.
 *
 * A fixture faz três remanejamentos diretos pela UGP (dois em Diárias, um em
 * Material gráfico). A tela lê `GET /api/v1/sgd/remanejamentos/transferencias/`;
 * cada linha é comparada com a resposta da API e as contagens, com o banco.
 * Território, período, responsável, documento e CSV esperam o backend
 * (pendencias-backend-sprint-12h.md, item 2), então não são testados aqui.
 */

let fx: HistoricoRemanejamentosFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarHistoricoRemanejamentosFixture();
});

test.afterAll(() => {
  removerHistoricoRemanejamentosFixture();
});

const LISTAGEM = "/api/v1/sgd/remanejamentos/transferencias/";

type Transferencia = {
  id: number;
  rubrica: string;
  valor: string;
  motivo: string;
  origem: { territorio: string | null; estado: string | null };
  destino: { territorio: string | null; estado: string | null };
  saldo_origem_antes: string;
  saldo_origem_depois: string;
  saldo_destino_antes: string;
  saldo_destino_depois: string;
  aprovado_por_nome: string | null;
};

function proximaListagem(page: Page, rubrica: string | null) {
  return page.waitForResponse((r) => {
    const url = new URL(r.url());
    return url.pathname === LISTAGEM && r.request().method() === "GET" && url.searchParams.get("rubrica") === rubrica;
  });
}

async function corpo(r: Promise<Response>) {
  return (await (await r).json()) as { count: number; results: Transferencia[] };
}

const brl = (v: string) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
/** O `Intl` separa "R$" do número com espaço sem quebra; o DOM pode trazer qualquer um dos dois. */
const normal = (s: string | null) => (s ?? "").replace(/\s/g, " ").trim();
const local = (p: Transferencia["origem"]) => p.territorio ?? p.estado ?? "Nacional";

async function conferirLinha(page: Page, t: Transferencia, rubrica: string) {
  const linha = `remanejamento-${t.id}`;
  await expect(page.getByTestId(`${linha}-pools`)).toHaveText(`${local(t.origem)} → ${local(t.destino)}`);
  await expect(page.getByTestId(`${linha}-rubrica`)).toHaveText(rubrica);
  await expect(page.getByTestId(`${linha}-origem`)).toHaveText("Direto da UGP");
  await expect(page.getByTestId(`${linha}-motivo`)).toHaveText(t.motivo);
  await expect(page.getByTestId(`${linha}-aprovado-por`)).toHaveText(t.aprovado_por_nome ?? "—");
  const texto = async (sufixo: string) => normal(await page.getByTestId(`${linha}-${sufixo}`).textContent());
  await expect.poll(() => texto("valor")).toBe(normal(brl(t.valor)));
  await expect
    .poll(() => texto("saldo-origem"))
    .toBe(normal(`${brl(t.saldo_origem_antes)}${brl(t.saldo_origem_depois)}`));
  await expect
    .poll(() => texto("saldo-destino"))
    .toBe(normal(`${brl(t.saldo_destino_antes)}${brl(t.saldo_destino_depois)}`));
}

test.describe("Histórico de remanejamentos (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("o Painel de Orçamento leva ao histórico, com saldos antes e depois de cada remanejamento", async ({ page }) => {
    await page.goto("/sgp/orcamento");
    const lista = proximaListagem(page, null);
    await page.getByTestId("orcamento-ir-historico-remanejamentos").click();
    await expect(page).toHaveURL(/\/sgp\/orcamento\/remanejamentos$/);
    const { count, results } = await corpo(lista);
    expect(count).toBe(fx.total);

    // Do mais recente ao mais antigo: os da fixture abrem a lista.
    const ids = results.map((t) => t.id);
    expect(ids.slice(0, 3)).toEqual([fx.grafico, ...[...fx.diarias].reverse()]);
    await expect(page.getByTestId("historico-remanejamentos-tabela").locator("tbody tr").first()).toHaveAttribute(
      "data-testid",
      `remanejamento-${fx.grafico}`,
    );
    for (const t of results.filter((r) => [...fx.diarias, fx.grafico].includes(r.id))) {
      await conferirLinha(page, t, t.id === fx.grafico ? "Material Gráfico" : "Diárias");
    }
    await expect(page.getByText(new RegExp(`de ${fx.total} remanejamentos?$`))).toBeVisible();
    await expect(page.getByTestId("historico-ir-remanejar")).toBeVisible();
  });

  test("o filtro por rubrica vai ao backend, fica na URL e sobrevive ao recarregar", async ({ page }) => {
    const inicial = proximaListagem(page, null);
    await page.goto("/sgp/orcamento/remanejamentos");
    await inicial;

    const filtrada = proximaListagem(page, "material-grafico");
    await page.locator("#historico-filtro-rubrica").click();
    await page.getByRole("option", { name: "Material Gráfico" }).click();
    expect((await corpo(filtrada)).count).toBe(fx.totalGrafico);
    await expect(page).toHaveURL(/[?&]rubrica=material-grafico(&|$)/);
    await expect(page.getByTestId(`remanejamento-${fx.grafico}`)).toBeVisible();
    for (const id of fx.diarias) await expect(page.getByTestId(`remanejamento-${id}`)).toHaveCount(0);

    const recarregada = proximaListagem(page, "material-grafico");
    await page.reload();
    expect((await corpo(recarregada)).count).toBe(fx.totalGrafico);
    await expect(page.locator("#historico-filtro-rubrica")).toContainText("Material Gráfico");

    const todas = proximaListagem(page, null);
    await page.locator("#historico-filtro-rubrica").click();
    await page.getByRole("option", { name: "Todas as rubricas" }).click();
    expect((await corpo(todas)).count).toBe(fx.total);
    await expect(page).not.toHaveURL(/[?&]rubrica=/);
  });

  test("um link além da última página volta para a última que existe", async ({ page }) => {
    await page.goto("/sgp/orcamento/remanejamentos?offset=1000");
    const ultima = Math.floor((fx.total - 1) / 20) * 20;
    await expect(page).toHaveURL(ultima > 0 ? new RegExp(`[?&]offset=${ultima}(&|$)`) : /\/remanejamentos$/);
    await expect(page.getByTestId("historico-remanejamentos-tabela")).toBeVisible();
  });
});

test.describe("Histórico de remanejamentos (FGD, leitura)", () => {
  test.use({ storageState: storageStatePath("fgd") });

  test("a FGD vê o histórico, mas não o Remanejar", async ({ page }) => {
    const lista = proximaListagem(page, null);
    await page.goto("/sgp/orcamento/remanejamentos");
    expect((await corpo(lista)).count).toBe(fx.total);
    await expect(page.getByTestId(`remanejamento-${fx.grafico}`)).toBeVisible();
    await expect(page.getByTestId("historico-ir-remanejar")).toHaveCount(0);
  });
});

test.describe("Histórico de remanejamentos (ADT)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o ADT recebe acesso restrito, sem chamar a listagem", async ({ page }) => {
    let chamou = false;
    page.on("request", (r) => {
      if (new URL(r.url()).pathname === LISTAGEM) chamou = true;
    });
    await page.goto("/sgp/orcamento/remanejamentos");
    await expect(page.getByText("Conteúdo restrito")).toBeVisible();
    await expect(page.getByText(/da FGD, que acompanha/)).toBeVisible();
    expect(chamou).toBe(false);
  });
});
