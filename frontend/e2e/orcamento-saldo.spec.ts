import { expect, test, type Page } from "@playwright/test";
import {
  criarOrcamentoFixture,
  definirPoolDoAdt,
  desvincularTerritorioDoAdt,
  removerOrcamentoFixture,
  revincularTerritorioDoAdt,
  rubricasComPoolDoAdt,
  RUBRICA_CRITICA,
} from "./helpers/orcamentoFixture";
import { RUBRICAS as CATALOGO } from "../app/lib/orcamento";
import { storageStatePath } from "./helpers/users";

/**
 * Saldo por rubrica no contexto do território (Issue #232), sobre o orçamento
 * por pool (#398): sem Meta, o saldo de cada rubrica é o do pool do território.
 *
 * O card só aparece para o ADT/ACR. `semPermissao` é o ADT da demonstração,
 * com território atribuído. A fixture do painel ajusta o pool territorial de
 * Diárias desse ADT (7.000 aprovado, 1.400 comprometido, 700 executado → 4.900
 * de saldo); este spec acrescenta o de Passagens esgotado (1.000 alocado, 800
 * comprometido, 200 executado → 0). As rubricas sem pool no território
 * aparecem bloqueadas, com saldo zero.
 *
 * Saldo negativo deixou de existir com a #384: o banco recusa pool com
 * comprometido mais executado acima do alocado (`ck_budget_pool_saldo_nao_negativo`).
 * O card ainda o destacaria, mas não há cenário real para o E2E.
 */

const RUBRICAS = CATALOGO.length;

/** Rubrica com pool no território, mas esgotado: bloqueada com saldo zero. */
const RUBRICA_ESGOTADA = { slug: "passagens-aereas", nome: "Passagens Aéreas" };

/** Rubricas sem pool no território do ADT: as que o card mostra zeradas e bloqueadas. */
let zeradas: string[] = [];

test.beforeAll(() => {
  criarOrcamentoFixture();
  definirPoolDoAdt(RUBRICA_ESGOTADA.slug, "1000.00", "800.00", "200.00");
  const comPool = rubricasComPoolDoAdt();
  zeradas = CATALOGO.map((r) => r.slug).filter((slug) => !comPool.includes(slug));
});

test.afterAll(() => {
  removerOrcamentoFixture();
});

/** Abre o painel e espera o card sair do skeleton. */
async function abrirCard(page: Page): Promise<void> {
  await page.goto("/sgp/orcamento/");
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

    expect(zeradas.length).toBeGreaterThan(0);
    for (const slug of zeradas) {
      await expect(
        page.getByTestId(`budget-balance-rubrica-${slug}`),
      ).toHaveAttribute("data-bloqueada", "true");
      await expect(page.getByTestId(`budget-balance-motivo-${slug}`)).toHaveText(
        /Bloqueado para novas solicitações quando saldo da rubrica é zero\./,
      );
    }

    // As sem pool mais a esgotada.
    await expect(page.getByTestId("budget-balance-resumo")).toHaveText(
      new RegExp(`${zeradas.length + 1} de ${RUBRICAS} rubricas bloqueadas`),
    );
  });

  test("pool esgotado aparece bloqueado com saldo zero, não some", async ({ page }) => {
    await abrirCard(page);
    const valor = page.getByTestId(`budget-balance-valor-${RUBRICA_ESGOTADA.slug}`);
    await expect(valor).toBeVisible();
    await expect(valor).toHaveText(/R\$\s*0,00/);
    await expect(page.getByTestId(`budget-balance-rubrica-${RUBRICA_ESGOTADA.slug}`)).toHaveAttribute(
      "data-bloqueada",
      "true",
    );
  });

  test("falha de rede exibe erro com ação de tentar novamente", async ({
    page,
  }) => {
    let derrubar = true;
    await page.route("**/api/v1/sgp/orcamento/painel/**", async (route) => {
      if (derrubar) {
        await route.abort("failed");
        return;
      }
      await route.continue();
    });

    await page.goto("/sgp/orcamento/");

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

    // Sem território, o card nem vai buscar o saldo — é isso que separa
    // "decidiu pela sessão" de "perguntou e recebeu vazio".
    await page.goto("/sgp/orcamento/");

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
      // O estado vazio vem do `code: "SEM_TERRITORIO"` do 403, com a
      // mensagem do backend.
      await expect(page.getByTestId("orcamento-sem-territorio")).toContainText(
        "Seu perfil de ADT/ACR ainda não tem território vinculado.",
      );

      // E o 403 não é apresentado como falha de rede: nada de "tentar
      // novamente", que aqui só repetiria a mesma negativa.
      await expect(page.getByTestId("budget-balance-erro")).toHaveCount(0);
    } finally {
      revincularTerritorioDoAdt(territorioId);
    }
  });
});
