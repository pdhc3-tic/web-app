import { expect, test, type Page } from "@playwright/test";
import {
  criarOrcamentoFixture,
  META_COM_ORCAMENTO,
  removerOrcamentoFixture,
  RUBRICA_CRITICA,
} from "./helpers/orcamentoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Saldo por rubrica no contexto do território (Issue #232).
 *
 * O card só aparece para o ADT/ACR — para os demais perfis a matriz já mostra
 * os mesmos números no nível que lhes cabe. `semPermissao` é justamente o ADT
 * da demonstração (ver `helpers/users.ts`), com território atribuído.
 *
 * Reaproveita a fixture do painel: ela cria uma alocação TERRITORIAL de Diárias
 * no território desse ADT (7.000 alocado, 1.400 comprometido, 700 executado →
 * 4.900 de saldo) e nada nas outras cinco rubricas. É o cenário que os dois
 * primeiros testes precisam — uma rubrica com saldo, cinco bloqueadas — sem
 * depender da data em que a suíte roda.
 */

const RUBRICAS = 6;

/** Slugs das cinco que ficam sem alocação territorial na fixture. */
const ZERADAS = [
  "passagens-aereas",
  "locacao-veiculo",
  "alimentacao-refeicoes",
  "material-grafico",
  "equipamentos-capital",
];

test.beforeAll(() => {
  criarOrcamentoFixture();
});

test.afterAll(() => {
  removerOrcamentoFixture();
});

/**
 * Resolve o ID da Meta a partir do NÚMERO.
 *
 * `META_COM_ORCAMENTO` é o número exibido ("Meta 1"), não a chave primária —
 * e o filtro da tela trabalha com o id. Ler da matriz já renderizada evita
 * fixar um id que muda a cada `seed_demo --reset`.
 */
async function idDaMeta(page: Page, numero: number): Promise<string> {
  const grupo = page
    .locator('[data-testid^="orcamento-meta-"]')
    .filter({ hasText: `Meta ${numero}` })
    .first();
  await expect(grupo).toBeVisible();
  const testid = await grupo.getAttribute("data-testid");
  return testid!.replace("orcamento-meta-", "");
}

/** Abre o painel filtrado na Meta da fixture e espera o card sair do skeleton. */
async function abrirCard(page: Page): Promise<void> {
  await page.goto("/sgp/orcamento/");
  const metaId = await idDaMeta(page, META_COM_ORCAMENTO);

  await page.goto(`/sgp/orcamento/?meta=${metaId}`);
  await expect(page.getByTestId("budget-balance")).toBeVisible();
  await expect(page.getByTestId("budget-balance-skeleton")).toHaveCount(0);
}

test.describe("Saldo por rubrica — ADT com território", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("exibe saldo das seis rubricas", async ({ page }) => {
    await abrirCard(page);

    const linhas = page.getByTestId("budget-balance-lista").getByRole("listitem");
    await expect(linhas).toHaveCount(RUBRICAS);

    // A rubrica com alocação territorial mostra o saldo, não o valor alocado:
    // 7.000 − 1.400 comprometido − 700 executado = 4.900.
    await expect(
      page.getByTestId(`budget-balance-valor-${RUBRICA_CRITICA.slug}`),
    ).toHaveText(/4\.900,00/);
  });

  test("rubrica zerada aparece bloqueada com a razão", async ({ page }) => {
    await abrirCard(page);

    // A que tem saldo NÃO está bloqueada — sem isto o teste passaria mesmo se
    // o card marcasse tudo como bloqueado.
    await expect(
      page.getByTestId(`budget-balance-rubrica-${RUBRICA_CRITICA.slug}`),
    ).toHaveAttribute("data-bloqueada", "false");
    await expect(
      page.getByTestId(`budget-balance-motivo-${RUBRICA_CRITICA.slug}`),
    ).toHaveCount(0);

    for (const slug of ZERADAS) {
      await expect(
        page.getByTestId(`budget-balance-rubrica-${slug}`),
      ).toHaveAttribute("data-bloqueada", "true");
      await expect(page.getByTestId(`budget-balance-motivo-${slug}`)).toHaveText(
        /Bloqueado para novas solicitações quando saldo da rubrica é zero\./,
      );
    }

    await expect(page.getByTestId("budget-balance-resumo")).toHaveText(
      /5 de 6 rubricas bloqueadas/,
    );
  });

  test("falha de rede exibe erro com ação de tentar novamente", async ({
    page,
  }) => {
    // O id sai da matriz, que vem do MESMO endpoint que este teste derruba —
    // por isso a interceptação só entra depois de resolvê-lo.
    await page.goto("/sgp/orcamento/");
    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);

    let derrubar = true;
    await page.route("**/api/v1/sgp/orcamento/painel/**", async (route) => {
      if (derrubar) {
        await route.abort("failed");
        return;
      }
      await route.continue();
    });

    await page.goto(`/sgp/orcamento/?meta=${metaId}`);

    const erro = page.getByTestId("budget-balance-erro");
    await expect(erro).toBeVisible();
    await expect(page.getByTestId("budget-balance-retry")).toBeVisible();

    // O retry precisa REALMENTE refazer a busca: solta a rede e clica.
    derrubar = false;
    await page.getByTestId("budget-balance-retry").click();

    await expect(page.getByTestId("budget-balance-lista")).toBeVisible();
    await expect(erro).toHaveCount(0);
  });
});

test.describe("Saldo por rubrica — ADT sem território", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  /**
   * O componente decide pela SESSÃO, não pela resposta da API: um ADT sem
   * território recebe 403 de `resolver_nivel_painel` com a mesma mensagem de
   * quem não tem acesso nenhum ao orçamento, e os dois casos pedem telas
   * diferentes. Por isso o teste esvazia `territorios` na sessão em vez de
   * mexer no banco — o token já foi emitido no login e não olharia o banco de
   * novo.
   */
  test("usuário sem território vê estado vazio, sem erro", async ({ page }) => {
    await page.route("**/api/auth/session", async (route) => {
      // O handler sobrevive ao fim do teste; sem o catch, a corrida entre a
      // última chamada da página e o teardown vira erro fora de qualquer teste.
      try {
        const resposta = await route.fetch();
        const sessao = await resposta.json();
        if (sessao?.user) {
          sessao.user.territorios = [];
        }
        await route.fulfill({ response: resposta, json: sessao });
      } catch {
        await route.abort("failed").catch(() => {});
      }
    });

    await page.goto("/sgp/orcamento/");

    const card = page.getByTestId("budget-balance");
    await expect(card).toBeVisible();
    await expect(card).toContainText("Nenhum território atribuído");

    // Estado vazio não é erro: nada de alerta nem de botão de retry.
    await expect(page.getByTestId("budget-balance-erro")).toHaveCount(0);
    await expect(page.getByTestId("budget-balance-lista")).toHaveCount(0);
  });
});
