import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Painel de Acompanhamento (FE-9) — semáforo por Ação.
 *
 * O semáforo é calculado pelo backend, em
 * `GET /api/v1/sgp/plano-trabalho/painel/`; a tela apenas o apresenta. Estes
 * testes cobrem a apresentação e os filtros, não a regra de classificação —
 * essa tem cobertura própria em `backend/apps/sgp/tests/test_workplan_dashboard.py`.
 *
 * ─── Por que o teste cria a Ação em vez de usar o seed ──────────────────────
 *
 * O semáforo compara o realizado com o tempo já decorrido do período, e todas
 * as Ações do `seed_demo` vão de 2025-01-01 a 2027-12-31. Um teste apoiado
 * nelas mudaria de resultado conforme a data em que roda — verde no começo do
 * projeto, vermelho perto do fim.
 *
 * A Ação criada aqui tem período INTEIRO NO PASSADO e nenhuma Atividade
 * vinculada: 0% realizado contra 100% esperado, razão zero. Fica vermelha em
 * qualquer data em que a suíte rode, e `em_atraso` pela mesma razão — prazo
 * vencido com entrega incompleta. Como o número da Ação é único apenas dentro
 * da Meta, "9.9" não colide com o seed — mesma tática de acoes.spec.ts.
 */

const META_NUMERO = 1;
const NUMERO_LIVRE = "9.9";
const DESCRICAO = "Ação crítica do E2E do painel";

/** Período encerrado: garante esperado = 100% independentemente de "hoje". */
const PERIODO_PASSADO = { inicio: "2024-01-01", fim: "2024-12-31" };

function tabelaMetas(page: Page): Locator {
  return page.getByTestId("metas-table").locator("table");
}

async function abrirMeta(page: Page): Promise<void> {
  await page.goto("/sgp/metas");
  await tabelaMetas(page)
    .getByRole("link", { name: `Visualizar Meta ${META_NUMERO}` })
    .click();
  await page.waitForURL(/\/sgp\/metas\/\d+$/);
  await expect(page.getByTestId("meta-detalhe-page")).toBeVisible();
  // `meta-detalhe-page` envolve TAMBÉM o spinner de carregamento, então esperar
  // só por ele devolve o controle com a tabela ainda vazia — e um `count()`
  // feito nesse instante conclui "não há resíduo" quando há. A tabela é a
  // primeira coisa que só existe com os dados carregados. A Meta 1 sempre tem
  // Ações no seed, então ela nunca cai no empty state.
  await expect(page.getByTestId("acoes-table")).toBeVisible();
}

/** Linha da Ação do teste na tabela da Meta (vazia quando não existe). */
function linhaDaAcao(page: Page): Locator {
  return page
    .getByTestId("acoes-table")
    .locator('tr[data-testid^="acao-row-"]')
    .filter({ hasText: DESCRICAO });
}

/**
 * Remove sobras de execuções interrompidas.
 *
 * Sem isto, um run que morreu no meio deixa a Ação "9.9" no banco e o próximo
 * falha na criação com "Já existe uma Ação com este número nesta Meta" — um
 * erro que não diz nada sobre o que está sendo testado.
 */
async function limparResiduo(page: Page): Promise<void> {
  const linha = linhaDaAcao(page);
  if ((await linha.count()) === 0) return;

  const testid = await linha.getAttribute("data-testid");
  const id = testid?.replace("acao-row-", "");
  if (!id) return;

  await excluirAcao(page, id);
}

/**
 * Exclui a Ação pelo botão da linha da tabela.
 *
 * O botão é buscado DENTRO da linha: a AcoesTable renderiza a mesma Ação duas
 * vezes — na tabela (desktop) e no card (mobile) —, e as duas cópias carregam o
 * mesmo `data-testid`. Procurar na página inteira viola o strict mode.
 */
async function excluirAcao(page: Page, id: string): Promise<void> {
  await page
    .getByTestId(`acao-row-${id}`)
    .getByTestId(`acao-excluir-btn-${id}`)
    .click();
  await page.getByTestId("acao-excluir-confirmar").click();
  await expect(page.getByTestId(`acao-row-${id}`)).toHaveCount(0);
}

/** Cria a Ação crítica pela UI e devolve o id que o backend atribuiu. */
async function criarAcaoCritica(page: Page): Promise<string> {
  await abrirMeta(page);
  await limparResiduo(page);

  await page.getByTestId("acao-nova-btn").click();
  await expect(page.getByTestId("acao-form")).toBeVisible();

  await page.getByTestId("acao-form-numero").fill(NUMERO_LIVRE);
  await page.getByTestId("acao-form-descricao").fill(DESCRICAO);

  const tipo = page.getByTestId("acao-form-tipo-unidade");
  await tipo.locator('button[role="combobox"]').click();
  await tipo
    .locator('li[role="option"]')
    .filter({ hasText: /^Oficina$/ })
    .click();

  await page.getByTestId("acao-form-quantidade").fill("100");
  await page.getByTestId("acao-form-valor-unitario").fill("10000");
  await page.getByTestId("acao-form-data-inicio").fill(PERIODO_PASSADO.inicio);
  await page.getByTestId("acao-form-data-fim").fill(PERIODO_PASSADO.fim);

  await page.getByTestId("acao-form-submit").click();
  await expect(page.getByTestId("acao-form")).toBeHidden();

  const linha = linhaDaAcao(page);
  await expect(linha).toBeVisible();

  const testid = await linha.getAttribute("data-testid");
  const id = testid?.replace("acao-row-", "");
  expect(id, "não foi possível descobrir o id da Ação criada").toBeTruthy();
  return id!;
}

/** Remove a Ação criada. Silencioso se ela já não existir. */
async function excluirAcaoCritica(page: Page, acaoId: string): Promise<void> {
  await abrirMeta(page);
  if ((await page.getByTestId(`acao-row-${acaoId}`).count()) === 0) return;
  await excluirAcao(page, acaoId);
}

test.describe("Painel de Acompanhamento — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  let acaoId: string;

  test.beforeEach(async ({ page }) => {
    acaoId = await criarAcaoCritica(page);
  });

  test.afterEach(async ({ page }) => {
    if (acaoId) await excluirAcaoCritica(page, acaoId);
  });

  test("Ação com progresso abaixo de 50% do esperado aparece na seção de alerta com badge vermelho", async ({
    page,
  }) => {
    await page.goto("/sgp/painel");
    await expect(page.getByTestId("painel-page")).toBeVisible();

    const alerta = page.getByTestId("painel-alerta");
    await expect(alerta).toBeVisible();
    await expect(alerta).toContainText("Ações que exigem atenção");

    const linha = alerta.getByTestId(`painel-acao-${acaoId}`);
    await expect(linha).toBeVisible();
    await expect(linha).toContainText(DESCRICAO);

    // O nível é o do semáforo, não a cor lida da tela: o teste de cores vive em
    // semaforo.spec.ts, e duplicá-lo aqui só acoplaria este teste à paleta.
    await expect(linha).toHaveAttribute("data-nivel", "vermelho");
    await expect(
      linha.getByTestId("semaforo-badge"),
    ).toHaveAttribute("data-nivel", "vermelho");

    // 0 de 100, contra um período inteiramente vencido.
    await expect(linha).toContainText("0 de 100");
    await expect(linha).toContainText("0,0% de 100,0% esperado");
  });

  test("clique em uma Ação do painel abre o detalhe e navega até a tela de edição", async ({
    page,
  }) => {
    await page.goto("/sgp/painel");
    await expect(page.getByTestId("painel-page")).toBeVisible();

    await page.getByTestId(`painel-acao-${acaoId}`).first().click();

    const detalhe = page.getByTestId("painel-acao-detalhe");
    await expect(detalhe).toBeVisible();
    await expect(detalhe).toContainText(DESCRICAO);

    await page.getByTestId("painel-acao-editar").click();

    await page.waitForURL(new RegExp(`/sgp/metas/\\d+\\?acao=${acaoId}$`));
    // O deep-link não só navega: abre a Ação certa já no formulário de edição.
    await expect(page.getByTestId("acao-form")).toBeVisible();
    await expect(page.getByTestId("acao-form-numero")).toHaveValue(
      NUMERO_LIVRE,
    );
  });

  test("filtrar por outra Meta remove a Ação do painel", async ({ page }) => {
    await page.goto("/sgp/painel");
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(1);

    const filtro = page.locator("#painel-filtro-meta");
    await filtro.click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: /^Meta 2 – / })
      .click();

    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(0);

    await page.getByTestId("painel-limpar-filtros").click();
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(1);
  });

  test("filtrar por situação usa o status_execucao calculado pelo backend", async ({
    page,
  }) => {
    await page.goto("/sgp/painel");
    // A Ação é procurada dentro do alerta: reduzir o painel a uma única Meta
    // abre o card por padrão, e aí a mesma Ação aparece no alerta E na lista.
    // O que este teste mede é o recorte do filtro, não quantas vezes a linha é
    // desenhada.
    const noAlerta = page
      .getByTestId("painel-alerta")
      .getByTestId(`painel-acao-${acaoId}`);
    await expect(noAlerta).toHaveCount(1);

    const filtro = page.locator("#painel-filtro-situacao");

    // A Ação tem prazo vencido e entrega zerada: está "Em atraso", nunca
    // "Concluída". Filtrar pelo oposto tem de tirá-la da tela inteira.
    await filtro.click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: /^Concluída$/ })
      .click();
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(0);

    await filtro.click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: /^Em atraso$/ })
      .click();
    await expect(noAlerta).toHaveCount(1);
  });

  test("os filtros ficam na URL e sobrevivem ao recarregamento", async ({
    page,
  }) => {
    await page.goto("/sgp/painel");
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(1);

    await page.locator("#painel-filtro-meta").click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: /^Meta 2 – / })
      .click();

    await page.waitForURL(/\/sgp\/painel\?.*meta=\d+/);
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(0);

    // O recorte é o estado da tela: recarregar não pode devolver "todas as
    // Metas", senão o link compartilhado não vale nada.
    await page.reload();
    await expect(page.getByTestId("painel-page")).toBeVisible();
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(0);
    await expect(page.getByTestId("painel-limpar-filtros")).toBeVisible();
  });
});
