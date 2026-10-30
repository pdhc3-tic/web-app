import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import {
  DESCRICAO_ACAO_CRITICA as DESCRICAO,
  criarAcaoCritica,
  removerAcaoCritica,
  type AcaoCritica,
} from "./helpers/painelFixture";

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
 * A Ação da fixture (`painelFixture.ts`) tem período INTEIRO NO PASSADO e
 * nenhuma Atividade vinculada: 0% realizado contra 100% esperado, razão zero.
 * Fica vermelha em qualquer data em que a suíte rode, e `em_atraso` pela mesma
 * razão — prazo vencido com entrega incompleta.
 */

test.describe("Painel de Acompanhamento — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });
  test.describe.configure({ mode: "serial" });

  let acao: AcaoCritica;
  let acaoId: string;

  test.beforeAll(() => {
    acao = criarAcaoCritica();
    acaoId = String(acao.id);
  });

  test.afterAll(() => {
    removerAcaoCritica();
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
      acao.numero,
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
      .filter({ hasText: /^Concluída$/i })
      .click();
    await expect(page.getByTestId(`painel-acao-${acaoId}`)).toHaveCount(0);

    await filtro.click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: /^Em atraso$/i })
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
