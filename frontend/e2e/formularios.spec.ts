import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

/**
 * Aba "Formulários" na ficha da UPF (#178) — testa integração da tabela +
 * modal de detalhe (#179) + empty state com CTA (stub, wire em #181) +
 * filtros (#180: formulário, período, respondente + URL sync).
 *
 * O seed_demo (#193) hoje NÃO cria FormResponse — portanto todo cenário
 * "com respostas" fica marcado como `.fixme` até um seed cobrir a demo.
 */

test.describe("SGP — Aba Formulários na UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("UPF sem respostas exibe empty state com CTA de preenchimento", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#formularios`);

    // Aguarda a ficha carregar — sem isto a aba pode ainda estar mostrando o
    // skeleton do fetch da UPF.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // A aba "Formulários" precisa aparecer no tablist (critério da issue).
    const abaFormularios = page.getByRole("tab", { name: "Formulários" });
    await expect(abaFormularios).toBeVisible();

    // #formularios já ativa a aba via useHashTab — o CTA do empty state deve
    // aparecer sem clique adicional.
    const cta = page.getByTestId("formularios-preencher-novo");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveText(/Preencher novo formulário/i);

    // Os filtros (#180) precisam estar renderizados mesmo em empty state,
    // pra permitir busca antes que haja resultado.
    await expect(page.getByTestId("formularios-filtros")).toBeVisible();
  });

  test("clique no CTA \"Preencher novo formulário\" abre o seletor de formulários", async ({
    page,
  }) => {
    // Verifica só a abertura do SlideOver — não depende de seed de
    // FormularioSGF, o SlideOver mostra empty state se não houver forms.
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#formularios`);

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByTestId("formularios-preencher-novo").click();

    await expect(
      page.getByTestId("preencher-formulario-slideover"),
    ).toBeVisible();
  });

  test.fixme(
    "escolher formulário no seletor navega para o placeholder do motor SGF",
    async ({ page }) => {
      // Depende de FormularioSGF publicado no seed — ainda não coberto.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);
      await page.getByTestId("formularios-preencher-novo").click();

      const seletor = page.getByTestId("preencher-formulario-slideover");
      const primeiraOpcao = seletor
        .locator('[data-testid^="formulario-disponivel-"]')
        .first();
      await expect(primeiraOpcao).toBeVisible();

      const testId = await primeiraOpcao.getAttribute("data-testid");
      const formularioId = testId?.replace("formulario-disponivel-", "");
      expect(formularioId).toBeTruthy();

      await primeiraOpcao.click();
      await expect(page).toHaveURL(
        new RegExp(`/sgf/formularios/${formularioId}/preencher\\?upf=${upfId}$`),
      );
      await expect(
        page.getByTestId("preencher-formulario-placeholder"),
      ).toBeVisible();
    },
  );

  test.fixme(
    "tabela ordena por data decrescente e clicar em linha abre o modal de detalhe",
    async ({ page }) => {
      // Depende de FormResponse no seed_demo — ainda não implementado. Assim
      // que o seed cobrir, remover o .fixme e ancorar por `respostas_json`
      // conhecido (ex.: um campo `atividade_principal`) na assertion do modal.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);

      const linhas = page.locator('tr[data-testid^="formulario-row-"]');
      await expect(linhas.first()).toBeVisible();
      await linhas.first().click();

      const modal = page.getByTestId("resposta-formulario-slideover");
      await expect(modal).toBeVisible();
    },
  );

  test.fixme(
    "filtro por período restringe as respostas ao intervalo escolhido",
    async ({ page }) => {
      // Depende de seed com múltiplas FormResponses em datas conhecidas.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);

      const linhas = page.locator('tr[data-testid^="formulario-row-"]');
      await expect(linhas.first()).toBeVisible();
      const totalAntes = await linhas.count();

      const hoje = new Date().toISOString().slice(0, 10);
      await page.getByLabel("De", { exact: true }).fill(hoje);
      await page.getByLabel("Até", { exact: true }).fill(hoje);

      // URL deve refletir os filtros aplicados (critério explícito).
      await expect(page).toHaveURL(
        new RegExp(`data_inicio=${hoje}&data_fim=${hoje}`),
      );

      const totalDepois = await linhas.count();
      expect(totalDepois).toBeLessThanOrEqual(totalAntes);
    },
  );

  test.fixme(
    "filtro por formulário específico restringe às respostas daquele formulário",
    async ({ page }) => {
      // Depende de seed com respostas em >1 formulário distinto.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);

      const linhas = page.locator('tr[data-testid^="formulario-row-"]');
      await expect(linhas.first()).toBeVisible();

      // Abre o select "Formulário" e escolhe a primeira opção não-vazia.
      const selectFormulario = page.getByRole("combobox", {
        name: "Formulário",
      });
      await selectFormulario.click();
      const opcao = page
        .locator('li[role="option"]')
        .filter({ hasNotText: /^Todos$/ })
        .first();
      const nomeAlvo = (await opcao.innerText()).trim();
      await opcao.click();

      // URL sincroniza com `formulario_id=`.
      await expect(page).toHaveURL(/formulario_id=\d+/);

      // Todas as linhas exibidas devem ser do formulário escolhido.
      const total = await linhas.count();
      for (let i = 0; i < total; i++) {
        await expect(linhas.nth(i).locator("td").first()).toContainText(
          nomeAlvo,
        );
      }
    },
  );

  test.fixme(
    "combinar filtro de período + respondente restringe corretamente",
    async ({ page }) => {
      // Depende de seed com respostas variando data e respondente conhecidos.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);

      const linhas = page.locator('tr[data-testid^="formulario-row-"]');
      await expect(linhas.first()).toBeVisible();

      const hoje = new Date().toISOString().slice(0, 10);
      await page.getByLabel("De", { exact: true }).fill(hoje);
      await page.getByLabel("Até", { exact: true }).fill(hoje);
      await page
        .getByLabel("Respondente", { exact: true })
        .fill("Técnico de campo");

      await expect(page).toHaveURL(
        new RegExp(
          `formulario_id=|data_inicio=${hoje}.*data_fim=${hoje}.*respondente=T`,
        ),
      );
    },
  );
});
