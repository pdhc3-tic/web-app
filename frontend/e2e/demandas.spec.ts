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
 * Contra o backend real. Os filtros por atividade (BE-5, PR #332) e de busca
 * de atividades (PR #328), antes pendências 6 e 9, já existem: os testes
 * conferem o parâmetro enviado e o recorte devolvido pelo servidor.
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

/** Criada, a demanda segue para a montagem (#295); a aba da atividade a lista em Rascunho. */
async function esperarMontagemEVoltarAAba(page: Page, titulo: string, atividadeId: number) {
  await page.waitForURL(/\/sgd\/demandas\/\d+\/editar$/);
  await expect(page.getByTestId("montar-demanda")).toContainText(titulo);
  await page.goto(`/sgp/atividades/${atividadeId}?tab=demandas`);
  await expect(linhaDaDemanda(page, titulo)).toContainText("Rascunho");
  await expect(linhaDaDemanda(page, titulo).getByText("Editar e submeter")).toBeVisible();
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

    await esperarMontagemEVoltarAAba(page, titulo, fx.agendada.id);
  });

  test("o contexto herdado mostra território, comunidade, data e a cadeia completa do PT", async ({
    page,
  }) => {
    await page.goto(`/sgd/demandas/nova?atividade=${fx.completa.id}`);
    const contexto = page.getByTestId("demanda-contexto");
    await expect(contexto).toContainText(fx.completa.titulo);

    const esperado: [string, string | RegExp][] = [
      ["Território", fx.territorio],
      ["Município", fx.municipio],
      ["Comunidade", fx.completa.comunidade],
      ["Data prevista", /\d{2}\/\d{2}\/\d{4}/],
      ["Técnico", fx.tecnico],
      ["Ação", `${fx.acao.numero} — ${fx.acao.descricao}`],
      ["Submeta", `${fx.submeta.numero} — ${fx.submeta.titulo}`],
      ["Meta", `Meta ${fx.meta.numero} — ${fx.meta.titulo}`],
      ["Indicador", `${fx.indicador.codigo} — ${fx.indicador.nome} (${fx.indicador.unidade_medida})`],
    ];
    for (const [rotulo, valor] of esperado) {
      const termo = contexto.locator("dt", { hasText: new RegExp(`^${rotulo}$`) });
      await expect(termo).toHaveCount(1);
      await expect(termo.locator("xpath=following-sibling::dd[1]")).toContainText(valor);
    }
    await expect(contexto).not.toContainText("Não disponível");
    // Somente leitura: nada editável no bloco herdado.
    await expect(contexto.locator("input, select, textarea, [role=combobox]")).toHaveCount(0);
  });

  test("no SGD, busca uma atividade agendada e cria a demanda vinculada a ela", async ({
    page,
  }) => {
    await page.goto("/sgd");
    await page.getByTestId("sgd-nova").click();
    await page.waitForURL("**/sgd/demandas/nova");

    const busca = page.waitForRequest(
      (req) => req.url().includes("/api/v1/sgp/atividades/?") && req.url().includes("q="),
    );
    await page.getByTestId("atividade-busca").fill("Oficina agendada");
    const params = new URL((await busca).url()).searchParams;
    // O contrato que o front manda: os dois status elegíveis, estreitados pelo
    // texto. Sem `tecnico_id` desde a #361 — vale qualquer atividade (#352).
    expect(params.has("tecnico_id")).toBe(false);
    expect(params.getAll("status")).toEqual(["planejado", "agendado"]);
    expect(params.get("q")).toBe("Oficina agendada");

    await page.getByRole("option", { name: new RegExp(fx.agendada.titulo) }).click();
    await expect(page.getByTestId("atividade-busca-escolhida")).toContainText(fx.agendada.titulo);
    await expect(page.getByTestId("demanda-contexto")).toContainText(fx.municipio);

    const titulo = `${PREFIXO} Lanche dos participantes`;
    await page.getByLabel("Título da demanda").fill(titulo);
    await page.getByTestId("nova-demanda-salvar").click();

    await esperarMontagemEVoltarAAba(page, titulo, fx.agendada.id);
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

    await page.waitForURL(/\/sgd\/demandas\/\d+\/editar$/);
    await page.getByRole("link", { name: "Abrir ficha da atividade" }).click();
    await page.waitForURL(/\/sgp\/atividades\/\d+\?tab=demandas$/);
    const novoId = Number(/atividades\/(\d+)/.exec(page.url())![1]);
    expect([fx.agendada.id, fx.comDemandas.id, fx.outra.id]).not.toContain(novoId);

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(tituloAtividade);
    await expect(page.getByText("Planejado").first()).toBeVisible();
    await expect(linhaDaDemanda(page, titulo)).toContainText("Rascunho");
  });

  // #361: a recusa do backend na atividade nova fica no campo do mini-formulário.
  test("criando a atividade, o erro de validação do backend aparece no campo dela", async ({
    page,
  }) => {
    await page.goto("/sgd/demandas/nova");
    await page.getByLabel("A atividade ainda não existe").check();

    // O campo não limita no cliente: quem recusa os 256 caracteres é o backend.
    await page.getByLabel("Título da atividade").fill(`${PREFIXO} ${"x".repeat(255)}`);
    await escolher(page, "nova-atividade-tipo", "Oficina");
    await page.getByLabel("Data prevista").fill("2026-11-20");
    await escolher(page, "nova-atividade-acao", new RegExp(`^${fx.acao.numero.replace(".", "\\.")} `));
    await escolher(page, "nova-atividade-municipio", fx.municipio);
    await page.getByLabel("Título da demanda").fill(`${PREFIXO} Demanda que não nasce`);

    const resposta = page.waitForResponse(
      (r) => r.url().includes("/api/v1/sgd/demandas/") && r.request().method() === "POST",
    );
    await page.getByTestId("nova-demanda-salvar").click();
    expect((await resposta).status()).toBe(400);

    const campo = page.getByTestId("nova-atividade-campos");
    await expect(campo.getByText(/255/)).toBeVisible();
    await expect(page.getByTestId("nova-demanda-erro")).toHaveCount(0);
    await expect(page).toHaveURL(/\/sgd\/demandas\/nova$/);
  });

  test("atividade com várias demandas lista todas, cada uma com o seu status", async ({
    page,
  }) => {
    const listagem = page.waitForRequest((req) =>
      req.url().includes("/api/v1/sgd/demandas/?"),
    );
    await page.goto(`/sgp/atividades/${fx.comDemandas.id}?tab=demandas`);
    const params = new URL((await listagem).url()).searchParams;
    expect(params.get("atividade")).toBe(String(fx.comDemandas.id));

    for (const d of fx.comDemandas.demandas) {
      await expect(linhaDaDemanda(page, d.titulo)).toContainText(d.status_display);
    }
  });

  // Item 6 das pendências, resolvido pelo filtro `atividade` do BE-5 (PR #332).
  test("a aba não lista a demanda de outra atividade", async ({ page }) => {
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

  // #404: custo da atividade no cabeçalho da aba e bloco de riscos de glosa (ver `custo` na fixture).
  test("o cabeçalho da aba mostra o custo previsto e o realizado que o backend calcula", async ({ page }) => {
    await page.goto(`/sgp/atividades/${fx.custo.id}?tab=demandas`);
    await expect(page.getByTestId("atividade-custos")).toBeVisible();
    // Previsto: a Submetida (R$ 1.200). A Concluída sai do previsto e entra no realizado
    // pelo autorizado (R$ 800), não pelo pago (R$ 950): o excedente é risco de glosa.
    await expect(page.getByTestId("atividade-custo-previsto")).toHaveText(/R\$\s1\.200,00/);
    await expect(page.getByTestId("atividade-custo-realizado")).toHaveText(/R\$\s800,00/);
  });

  test("o bloco de riscos de glosa lista os riscos em aberto, com severidade e valor exposto", async ({ page }) => {
    const { pagoAcima, semEvidencia, resolvido } = fx.custo.riscos;
    await page.goto(`/sgp/atividades/${fx.custo.id}`);

    const bloco = page.getByTestId("riscos-de-glosa");
    await expect(bloco).toBeVisible();
    await expect(page.getByTestId("riscos-de-glosa-total")).toHaveText(/R\$\s1\.100,00/);

    const acima = page.getByTestId(`risco-de-glosa-${pagoAcima}`);
    await expect(acima).toContainText("Pago acima do autorizado");
    await expect(acima).toContainText("150,00");
    await expect(page.getByTestId(`risco-de-glosa-severidade-${pagoAcima}`)).toHaveText("Severidade alta");
    await expect(page.getByTestId(`risco-de-glosa-severidade-${pagoAcima}`)).toHaveAttribute(
      "data-severidade",
      "alta",
    );
    await expect(page.getByTestId(`risco-de-glosa-${semEvidencia}`)).toContainText(
      "Demanda executada sem evidência",
    );
    await expect(page.getByTestId(`risco-de-glosa-${semEvidencia}`)).toContainText("950,00");

    // Resolvido não é mais risco.
    await expect(page.getByTestId(`risco-de-glosa-${resolvido}`)).toHaveCount(0);
    await expect(bloco.locator('[data-testid^="risco-de-glosa-severidade-"]')).toHaveCount(2);
  });

  test("sem risco em aberto, a ficha não mostra o bloco", async ({ page }) => {
    // Espera a resposta da consulta, para não passar só porque ela ainda não voltou.
    const riscos = page.waitForResponse(
      (r) => r.url().includes(`/api/v1/sgp/glosa-riscos/?activity=${fx.comDemandas.id}`) && r.ok(),
    );
    await page.goto(`/sgp/atividades/${fx.comDemandas.id}`);
    await riscos;
    await expect(page.getByTestId("atividade-status-btn")).toBeVisible();
    await expect(page.getByTestId("riscos-de-glosa")).toHaveCount(0);
  });
});
