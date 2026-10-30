import { expect, test, type Page } from "@playwright/test";
import { abrirComApi, apiGet } from "./helpers/apiReal";
import { criarTecnicosFixture, removerTecnicosFixture, type TecnicosFixture } from "./helpers/tecnicosFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Técnicos do SGP (#237, A2 da #302), contra o backend real. O seed não traz
 * técnicos: o primeiro teste vê a tela vazia de verdade, e a fixture cria os
 * técnicos e usuários dos demais. Só a falha do servidor é forçada (500).
 */

test.describe.configure({ mode: "serial" });

const linha = (page: Page, nome: string) => page.getByRole("row", { name: new RegExp(nome) });
const painel = (page: Page) => page.locator('[role="dialog"]').first();

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao, exact: true }).click();
}

test.describe("SGP — Técnicos (UGP), sem técnicos cadastrados", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("estado vazio sem filtros oferece o cadastro", async ({ page }) => {
    const origem = await abrirComApi(page, "/sgp/tecnicos");
    const { count } = await apiGet<{ count: number }>(page, origem, "/api/v1/sgp/tecnicos/?limit=1");
    expect(count).toBe(0);
    await expect(page.getByText("Nenhum técnico cadastrado")).toBeVisible();
    await expect(page.getByRole("button", { name: "Adicionar técnico" }).first()).toBeVisible();
  });
});

test.describe("SGP — Técnicos com dados", () => {
  let fx: TecnicosFixture;

  test.beforeAll(() => {
    fx = criarTecnicosFixture();
  });

  test.afterAll(() => {
    removerTecnicosFixture();
  });

  test.describe("UGP", () => {
    test.use({ storageState: storageStatePath("ugp") });

    test("card Técnicos aparece na página do SGP com link funcional", async ({ page }) => {
      await page.goto("/sgp");
      const card = page.getByRole("link", { name: /Técnicos/i });
      await expect(card).toBeVisible();
      expect(await card.getAttribute("href")).toContain("/sgp/tecnicos");
    });

    test("listagem mostra nome, papel, território, OSC e situação vindos da API", async ({ page }) => {
      await page.goto("/sgp/tecnicos");
      await expect(page.getByRole("columnheader", { name: "Nome" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Papel" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Situação" })).toBeVisible();

      const ana = linha(page, fx.ana.nome);
      await expect(ana).toContainText(fx.ana.papel);
      await expect(ana).toContainText(fx.ana.territorio);
      if (fx.ana.osc) await expect(ana).toContainText(fx.ana.osc);
      await expect(ana).toContainText("Ativo");
      await expect(linha(page, fx.maria.nome)).toContainText("Inativo");
    });

    test("filtro sem resultado mostra 'Limpar filtros'", async ({ page }) => {
      await page.goto("/sgp/tecnicos?papel=Inexistente");
      await expect(page.getByText("Nenhum técnico encontrado")).toBeVisible();
      await page.getByRole("button", { name: "Limpar filtros" }).click();
      await expect(linha(page, fx.ana.nome)).toBeVisible();
    });

    test("cadastro: valida obrigatórios e cria o técnico buscando o usuário elegível no servidor", async ({ page }) => {
      await page.goto("/sgp/tecnicos");
      await page.getByRole("button", { name: "Adicionar técnico" }).first().click();
      await expect(painel(page).getByRole("heading", { name: "Novo técnico" })).toBeVisible();
      await painel(page).getByRole("button", { name: "Salvar" }).click();
      await expect(painel(page).getByText("Selecione o usuário.")).toBeVisible();
      await expect(painel(page).getByText("Informe o papel.")).toBeVisible();

      // A busca é no servidor (`usuarios-elegiveis/?q=`), e quem já é técnico não aparece.
      const busca = page.waitForRequest((r) => {
        const url = new URL(r.url());
        return url.pathname === "/api/v1/sgp/tecnicos/usuarios-elegiveis/" && url.searchParams.get("q") === "E2E-302";
      });
      await page.getByTestId("tecnico-usuario").fill("E2E-302");
      await busca;
      await expect(page.getByRole("option", { name: new RegExp(fx.elegivel.nome) })).toBeVisible();
      await expect(page.getByRole("option", { name: new RegExp(fx.ana.nome) })).toHaveCount(0);
      await page.getByRole("option", { name: new RegExp(fx.elegivel.nome) }).click();
      await page.locator("#tecnico-papel").fill("Agente de campo");

      const criacao = page.waitForResponse(
        (r) => new URL(r.url()).pathname === "/api/v1/sgp/tecnicos/" && r.request().method() === "POST",
      );
      await painel(page).getByRole("button", { name: "Salvar" }).click();
      expect((await criacao).status()).toBe(201);
      await expect(linha(page, fx.elegivel.nome)).toContainText("Agente de campo");
    });

    test("OSC fora do território: o backend recusa e a tela mostra a mensagem do código", async ({ page }) => {
      await page.goto("/sgp/tecnicos");
      await linha(page, fx.maria.nome).click();
      await expect(painel(page).getByRole("heading", { name: "Editar técnico" })).toBeVisible();
      await escolher(page, "tecnico-territorio", fx.conflito.territorio);
      await escolher(page, "tecnico-osc", fx.conflito.osc);

      const edicao = page.waitForResponse((r) => r.url().includes("/api/v1/sgp/tecnicos/") && r.request().method() !== "GET");
      await painel(page).getByRole("button", { name: "Salvar" }).click();
      expect((await edicao).status()).toBe(400);
      await expect(painel(page).getByText("A OSC selecionada não atua neste território.")).toBeVisible();
    });

    test("desativar pede confirmação e a linha passa a Inativo", async ({ page }) => {
      await page.goto("/sgp/tecnicos");
      await linha(page, fx.ana.nome).click();
      await painel(page).getByRole("button", { name: "Desativar" }).click();
      const confirmacao = page.locator('[role="dialog"]').last();
      await expect(confirmacao.getByRole("heading", { name: "Desativar técnico?" })).toBeVisible();

      const desativacao = page.waitForResponse((r) => r.url().endsWith(`/api/v1/sgp/tecnicos/${fx.ana.id}/`));
      await confirmacao.getByRole("button", { name: "Desativar" }).click();
      expect((await desativacao).status()).toBe(204);
      // Fecham os dois: o painel de edição e a confirmação por cima dele.
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(linha(page, fx.ana.nome)).toContainText("Inativo");
    });

    test("erro do servidor exibe a mensagem e 'Tentar novamente'", async ({ page }) => {
      // Falha forçada: o único caso em que a resposta é interceptada.
      await page.route("**/api/v1/sgp/tecnicos/?*", (route) =>
        route.request().method() === "GET"
          ? route.fulfill({ status: 500, headers: { "access-control-allow-origin": "*" }, body: "error" })
          : route.fallback(),
      );
      await page.goto("/sgp/tecnicos");
      await expect(page.getByText(/Erro inesperado \(500\)|Não foi possível carregar os técnicos/)).toBeVisible();
      await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
    });
  });

  test.describe("ADT (sem permissão de escrita)", () => {
    test.use({ storageState: storageStatePath("semPermissao") });

    test("vê os técnicos do seu território, sem 'Adicionar técnico', e abre só para visualizar", async ({ page }) => {
      await page.goto("/sgp/tecnicos");
      await expect(linha(page, fx.ana.nome)).toBeVisible();
      await expect(page.getByRole("button", { name: "Adicionar técnico" })).toHaveCount(0);

      await linha(page, fx.ana.nome).click();
      await expect(painel(page)).toBeVisible();
      await expect(painel(page).getByRole("button", { name: "Salvar" })).toHaveCount(0);
      await expect(painel(page).getByText(fx.ana.nome).first()).toBeVisible();
      await expect(painel(page).getByText(fx.ana.territorio).first()).toBeVisible();
    });
  });
});
