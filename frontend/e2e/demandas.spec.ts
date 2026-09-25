import { expect, test, type Page } from "@playwright/test";
import {
  criarDemandaFixture,
  PREFIXO,
  removerDemandaFixture,
  type DemandaFixture,
} from "./helpers/demandaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #294 — Aba "Demandas" na ficha da Atividade + criação de demanda (SGD).
 *
 * Contra o backend real. Duas asserções dependem de filtros que o backend
 * ainda não tem (docs/pendencias-backend-sprint-10.md, itens 6 e 9): os testes
 * provam que o front MANDA o filtro certo, e o comportamento do servidor fica
 * num `test.fixme` que passa a valer quando o filtro existir.
 */

let fx: DemandaFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarDemandaFixture();
});

test.afterAll(() => {
  removerDemandaFixture();
});

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

function linhaDaDemanda(page: Page, titulo: string) {
  return page.getByTestId("demandas-lista").locator("li").filter({ hasText: titulo });
}

test.describe("SGD — demandas pela ficha da atividade (ADT)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("a aba Demandas cria uma demanda com o contexto herdado, somente leitura", async ({
    page,
  }) => {
    await page.goto(`/sgp/atividades/${fx.agendada.id}?tab=demandas`);
    await expect(page.getByRole("tab", { name: "Demandas" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.getByTestId("demanda-nova-btn").click();
    await page.waitForURL(`**/sgd/demandas/nova?atividade=${fx.agendada.id}`);

    const contexto = page.getByTestId("demanda-contexto");
    await expect(contexto).toContainText(fx.agendada.titulo);
    await expect(contexto).toContainText(fx.municipio);
    await expect(contexto).toContainText(fx.tecnico);
    await expect(contexto).toContainText(`${fx.acao.numero} — ${fx.acao.descricao}`);
    // Somente leitura: nenhum controle editável dentro do bloco herdado.
    await expect(contexto.locator("input, select, textarea, [role=combobox]")).toHaveCount(0);
    // Vindo da ficha, a atividade está decidida: não há como trocá-la.
    await expect(page.getByTestId("atividade-busca")).toHaveCount(0);

    const titulo = `${PREFIXO} Diárias do facilitador`;
    await page.getByLabel("Título da demanda").fill(titulo);
    await page.getByTestId("nova-demanda-salvar").click();

    await page.waitForURL(`**/sgp/atividades/${fx.agendada.id}?tab=demandas`);
    await expect(linhaDaDemanda(page, titulo)).toContainText("Rascunho");
  });

  test("no SGD, busca uma atividade agendada e cria a demanda vinculada a ela", async ({
    page,
  }) => {
    await page.goto("/sgd");
    await page.getByTestId("sgd-nova-demanda").click();
    await page.waitForURL("**/sgd/demandas/nova");

    const busca = page.waitForRequest(
      (req) => req.url().includes("/api/v1/sgp/atividades/?") && req.url().includes("q="),
    );
    await page.getByTestId("atividade-busca").fill("Oficina agendada");
    const params = new URL((await busca).url()).searchParams;
    // O contrato que o front manda: só as atividades do solicitante, nos dois
    // status elegíveis, estreitadas pelo texto.
    expect(params.get("tecnico_id")).toBe(String(fx.tecnicoId));
    expect(params.getAll("status")).toEqual(["planejado", "agendado"]);
    expect(params.get("q")).toBe("Oficina agendada");

    await page.getByRole("option", { name: new RegExp(fx.agendada.titulo) }).click();
    await expect(page.getByTestId("atividade-escolhida")).toContainText(fx.agendada.titulo);
    await expect(page.getByTestId("demanda-contexto")).toContainText(fx.municipio);

    const titulo = `${PREFIXO} Lanche dos participantes`;
    await page.getByLabel("Título da demanda").fill(titulo);
    await page.getByTestId("nova-demanda-salvar").click();

    await page.waitForURL(`**/sgp/atividades/${fx.agendada.id}?tab=demandas`);
    await expect(linhaDaDemanda(page, titulo)).toContainText("Rascunho");
  });

  test("sem atividade prévia, cria a atividade em Planejado junto com a demanda", async ({
    page,
  }) => {
    await page.goto("/sgd/demandas/nova");
    await page.getByLabel("A atividade ainda não existe").check();

    const tituloAtividade = `${PREFIXO} Visita criada com a demanda`;
    await page.getByLabel("Título da atividade").fill(tituloAtividade);
    await escolher(page, "nova-atividade-tipo", "Oficina");
    await page.getByLabel("Data prevista").fill("2026-11-20");
    await escolher(page, "nova-atividade-acao", new RegExp(`^${fx.acao.numero.replace(".", "\\.")} `));
    await escolher(page, "nova-atividade-municipio", fx.municipio);

    const titulo = `${PREFIXO} Combustível da visita`;
    await page.getByLabel("Título da demanda").fill(titulo);
    await page.getByTestId("nova-demanda-salvar").click();

    await page.waitForURL(/\/sgp\/atividades\/\d+\?tab=demandas$/);
    const novoId = Number(/atividades\/(\d+)/.exec(page.url())![1]);
    expect([fx.agendada.id, fx.comDemandas.id, fx.outra.id]).not.toContain(novoId);

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(tituloAtividade);
    await expect(page.getByText("Planejado").first()).toBeVisible();
    await expect(linhaDaDemanda(page, titulo)).toContainText("Rascunho");
  });

  test("atividade com várias demandas lista todas, cada uma com o seu status", async ({
    page,
  }) => {
    const listagem = page.waitForRequest((req) =>
      req.url().includes("/api/v1/sgd/demandas/?"),
    );
    await page.goto(`/sgp/atividades/${fx.comDemandas.id}?tab=demandas`);
    const params = new URL((await listagem).url()).searchParams;
    expect(params.get("activity")).toBe(String(fx.comDemandas.id));

    for (const d of fx.comDemandas.demandas) {
      await expect(linhaDaDemanda(page, d.titulo)).toContainText(d.status_display);
    }
  });

  // Depende do filtro `?activity=` no DemandViewSet.list — pendência de backend
  // (docs/pendencias-backend-sprint-10.md, item 6). Hoje o backend ignora o
  // parâmetro e a aba mostra todas as demandas visíveis ao usuário.
  test.fixme("a aba não lista a demanda de outra atividade", async ({ page }) => {
    await page.goto(`/sgp/atividades/${fx.comDemandas.id}?tab=demandas`);
    await expect(linhaDaDemanda(page, fx.comDemandas.demandas[0].titulo)).toBeVisible();
    await expect(page.getByText(fx.outra.demanda)).toHaveCount(0);
  });
});

test.describe("SGD — perfis que não abrem demanda", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("UGP vê as demandas, mas não o botão de criar nem o formulário", async ({ page }) => {
    await page.goto(`/sgp/atividades/${fx.comDemandas.id}?tab=demandas`);
    await expect(page.getByTestId("atividade-demandas")).toBeVisible();
    await expect(page.getByTestId("demanda-nova-btn")).toHaveCount(0);

    await page.goto("/sgd/demandas/nova");
    await expect(page.getByTestId("nova-demanda-form")).toHaveCount(0);
  });
});
