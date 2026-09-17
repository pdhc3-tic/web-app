import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  criarOrcamentoFixture,
  desvincularTerritorioDoAdt,
  META_COM_ORCAMENTO,
  removerOrcamentoFixture,
  revincularTerritorioDoAdt,
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

/** Rubrica que este spec deixa com saldo negativo. Ver `criarSaldoNegativo`. */
const RUBRICA_NEGATIVA = { slug: "passagens-aereas", nome: "Passagens Aéreas" };

/** Slugs das quatro que ficam sem alocação territorial na fixture. */
const ZERADAS = [
  "locacao-veiculo",
  "alimentacao-refeicoes",
  "material-grafico",
  "equipamentos-capital",
];

/**
 * Saldo negativo no território do ADT: 1.000 alocado, 1.500 comprometido.
 *
 * Fica NESTE spec, e não na `orcamentoFixture` compartilhada, porque uma
 * alocação a 150% acende o semáforo vermelho — e `orcamento.spec.ts` afirma
 * que o ADT não vê banner de alerta. Semear lá quebraria aquela suíte.
 *
 * Não há como produzir o cenário pela interface: a tela de distribuição recusa
 * reduzir abaixo do comprometido. O ORM cru é o mesmo caminho da fixture
 * compartilhada, e o teardown dela apaga esta linha junto (filtra por Meta).
 */
function criarSaldoNegativo(): void {
  execFileSync(
    "docker",
    [
      "compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c",
      `
from decimal import Decimal
from apps.core.models.user_profile import UserProfile
from apps.sgp.models import BudgetAllocation, BudgetRubrica, WorkPlanMeta

perfil = (
    UserProfile.objects.select_related("territorio")
    .filter(user__email="marina.albuquerque@demo.pdhc.local", perfil__slug="adt-acr")
    .exclude(territorio__isnull=True)
    .first()
)
if perfil is None:
    raise RuntimeError("ADT dos E2E sem territorio: rode manage.py seed_demo")

BudgetAllocation.objects.update_or_create(
    meta=WorkPlanMeta.objects.get(numero=${META_COM_ORCAMENTO}),
    rubrica=BudgetRubrica.objects.get(slug="${RUBRICA_NEGATIVA.slug}"),
    nivel="territorial", estado=None, territorio=perfil.territorio,
    defaults={
        "valor_alocado": Decimal("1000.00"),
        "valor_comprometido": Decimal("1500.00"),
        "valor_executado": Decimal("200.00"),
    },
)
`,
    ],
    { cwd: path.resolve(__dirname, ".."), encoding: "utf8", timeout: 120_000 },
  );
}

test.beforeAll(() => {
  criarOrcamentoFixture();
  criarSaldoNegativo();
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

  test("saldo negativo aparece em destaque, nunca escondido", async ({
    page,
  }) => {
    await abrirCard(page);

    const valor = page.getByTestId(
      `budget-balance-valor-${RUBRICA_NEGATIVA.slug}`,
    );
    // O valor é EXIBIDO — o critério é explícito em não escondê-lo.
    await expect(valor).toBeVisible();
    await expect(valor).toHaveText(/-\s?R\$\s*700,00|R\$\s*-700,00/);

    // E fica bloqueada, com a razão dizendo que veio de remanejamento.
    await expect(
      page.getByTestId(`budget-balance-rubrica-${RUBRICA_NEGATIVA.slug}`),
    ).toHaveAttribute("data-bloqueada", "true");
    await expect(
      page.getByTestId(`budget-balance-motivo-${RUBRICA_NEGATIVA.slug}`),
    ).toContainText(/Saldo negativo por remanejamento/i);
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
   * "Sem território" tem DOIS caminhos, e eles precisam de testes separados.
   *
   * Antes havia só o primeiro, e ele era um falso positivo enquanto era o
   * único: esvaziava `territorios` na resposta da sessão, mas o banco continuava
   * com o território da Marina, então `resolver_nivel_painel` respondia 200 e
   * nenhum 403 chegava à página. O que passava era o ramo em que o COMPONENTE
   * decide pela sessão — nunca o caminho real, em que a API nega e a PÁGINA
   * precisa sobreviver à negativa. E era justamente ali que estava o defeito:
   * a tela de orçamento convertia aquele 403 em `RestrictedAccess`, e o card
   * com o estado vazio explicativo sequer chegava a renderizar.
   *
   * O primeiro teste continua valendo pelo que de fato cobre, com o banco
   * INTACTO; o segundo remove o vínculo de verdade e cobre o resto.
   */
  test("sessão sem território decide sem gastar requisição", async ({
    page,
  }) => {
    const chamadasAoPainel: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/v1/sgp/orcamento/painel/")) {
        chamadasAoPainel.push(req.url());
      }
    });

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

    // COM filtro de Meta: sem território, o card nem assim vai buscar o saldo —
    // é isso que separa "decidiu pela sessão" de "perguntou e recebeu vazio".
    await page.goto("/sgp/orcamento/");
    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);
    chamadasAoPainel.length = 0;
    await page.goto(`/sgp/orcamento/?meta=${metaId}`);

    const card = page.getByTestId("budget-balance");
    await expect(card).toBeVisible();
    await expect(card).toContainText("Nenhum território atribuído");

    // Estado vazio não é erro: nada de alerta nem de botão de retry.
    await expect(page.getByTestId("budget-balance-erro")).toHaveCount(0);
    await expect(page.getByTestId("budget-balance-lista")).toHaveCount(0);

    // A página em volta chama o painel uma vez para montar a matriz. O card não
    // acrescenta a segunda: ele já sabia a resposta antes de perguntar.
    expect(chamadasAoPainel.length).toBeLessThanOrEqual(1);
  });

  /**
   * O caminho que o falso positivo escondia: a API nega de verdade.
   *
   * O vínculo é removido no BANCO — só assim `resolver_nivel_painel` devolve
   * 403. A sessão não é tocada: o JWT do storageState ainda carrega o território
   * antigo, porque `territorios` é gravado no login e nunca mais relido (ver
   * auth.ts). É exatamente o que acontece com quem tem o vínculo desfeito no
   * meio da sessão.
   *
   * O `finally` repõe o território mesmo se a asserção falhar: sem ele, todas as
   * outras specs do ADT quebrariam em cascata.
   */
  test("403 do painel não vira acesso restrito", async ({ page }) => {
    const territorioId = desvincularTerritorioDoAdt();
    try {
      const respostas: number[] = [];
      page.on("response", (res) => {
        if (res.url().includes("/api/v1/sgp/orcamento/painel/")) {
          respostas.push(res.status());
        }
      });

      await page.goto("/sgp/orcamento/");

      const card = page.getByTestId("budget-balance");
      await expect(card).toBeVisible();
      await expect(card).toContainText("Nenhum território atribuído");

      // A negativa aconteceu mesmo — é o que separa este teste do anterior.
      await expect(() => expect(respostas).toContain(403)).toPass();

      // O que a regressão produzia: a tela inteira trocada pelo acesso restrito.
      await expect(
        page.getByRole("heading", { name: "Conteúdo restrito" }),
      ).toHaveCount(0);
      await expect(page.getByTestId("orcamento-sem-territorio")).toBeVisible();

      // E o 403 não é apresentado como falha de rede: nada de "tentar
      // novamente", que aqui só repetiria a mesma negativa.
      await expect(page.getByTestId("budget-balance-erro")).toHaveCount(0);
    } finally {
      revincularTerritorioDoAdt(territorioId);
    }
  });
});
