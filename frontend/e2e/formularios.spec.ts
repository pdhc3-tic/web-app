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

    // Texto do aceite, palavra por palavra — sem filtro ativo o estado vazio
    // fala da família, não da busca.
    await expect(
      page.getByText("Nenhum formulário respondido para esta família ainda.", {
        exact: true,
      }),
    ).toBeVisible();

    // #formularios já ativa a aba via useHashTab — o CTA do empty state deve
    // aparecer sem clique adicional.
    const cta = page.getByTestId("formularios-preencher-novo");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveText(/Preencher novo formulário/i);

    // Os filtros (#180) precisam estar renderizados mesmo em empty state,
    // pra permitir busca antes que haja resultado.
    await expect(page.getByTestId("formularios-filtros")).toBeVisible();
  });

  test("com filtro ativo o estado vazio fala da busca, não do histórico da família", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    // Filtro que não casa com nada: o texto do aceite não pode aparecer aqui,
    // senão sugere que a família nunca respondeu formulário algum.
    await page.goto(`/sgp/upfs/${upfId}?respondente=zzz-inexistente#formularios`);

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(
      page.getByText("Nenhuma resposta com esses filtros", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Nenhum formulário respondido para esta família ainda.", {
        exact: true,
      }),
    ).toHaveCount(0);
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

  test("seletor sem formulários publicados mostra o texto exato do aceite", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // O seed pode ou não ter formulário publicado; o estado vazio é do
    // catálogo (BE-18), então fixamos a resposta para exercitá-lo sempre.
    await page.route(/\/api\/v1\/sgp\/formularios-disponiveis\/$/, (route) =>
      route.request().method() === "GET"
        ? route.fulfill({
            status: 200,
            contentType: "application/json",
            body: "[]",
          })
        : route.fallback(),
    );

    await page.goto(`/sgp/upfs/${upfId}#formularios`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByTestId("formularios-preencher-novo").click();

    const painel = page.getByTestId("preencher-formulario-slideover");
    await expect(painel).toBeVisible();
    await expect(
      painel.getByText(
        "Nenhum formulário disponível para vincular a famílias no momento.",
        { exact: true },
      ),
    ).toBeVisible();

    // Caminho de volta para a aba continua disponível. Busca por atributo, e
    // não por role: o backdrop que envolve o painel é `aria-hidden`, então o
    // rodapé com o "Cancelar" some das buscas na árvore de acessibilidade
    // (mesmo contorno usado em membros.spec.ts).
    await page
      .locator('[role="dialog"]')
      .locator("button", { hasText: "Cancelar" })
      .click();
    await expect(painel).toHaveCount(0);
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

/**
 * Opções do filtro por formulário (#180, item 4 do review).
 *
 * O `seed_demo` não cria nenhuma `FormResponse`, então a única forma de
 * exercitar "formulário cuja resposta está fora da primeira página" é fixar as
 * respostas do backend. As duas páginas abaixo colocam o formulário alvo só na
 * segunda — que é exatamente o caso que a derivação por página perdia.
 *
 * `/formularios/opcoes/` é fixado em 404 de propósito: isto cobre o fallback
 * paginado, o caminho usado enquanto a #214 não é implantada. Quando ela
 * subir, o select passa a vir do metadado não paginado e este teste segue
 * válido como regressão do fallback.
 */
test.describe("SGP — Opções do filtro de formulário", () => {
  test.use({ storageState: storageStatePath("ugp") });

  const PAGINA_1 = "Caderno de Visita";
  const PAGINA_2 = "Diagnóstico Produtivo";
  const ID_PAGINA_2 = 77;

  function resposta(id: number, formularioId: number, nome: string) {
    return {
      id,
      upf: 1,
      formulario_id: formularioId,
      formulario_nome: nome,
      formulario_versao: "1.0",
      contract_version: "1.0",
      resposta_id_origem: `orig-${id}`,
      data_preenchimento: "2026-08-20T10:00:00-03:00",
      respondente: "Técnico de campo",
      status: "submetido",
      origem: "web",
      criado_em: "2026-08-20T10:00:00-03:00",
    };
  }

  async function stubRespostasEmDuasPaginas(page: import("@playwright/test").Page) {
    await page.route(/\/formularios\/opcoes\/$/, (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ code: "not_found", message: "Não encontrado." }),
      }),
    );

    await page.route(/\/api\/v1\/sgp\/upfs\/\d+\/formularios\/(\?|$)/, async (route) => {
      const params = new URL(route.request().url()).searchParams;
      const page1 = (params.get("page") ?? "1") === "1";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 2,
          // `next` não-nulo é o que obriga a varredura a buscar a página 2.
          next: page1 ? "http://x/?page=2" : null,
          previous: null,
          results: page1
            ? [resposta(1, 55, PAGINA_1)]
            : [resposta(2, ID_PAGINA_2, PAGINA_2)],
        }),
      });
    });
  }

  test("formulário cuja resposta está fora da 1ª página aparece ao abrir a aba", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await stubRespostasEmDuasPaginas(page);

    await page.goto(`/sgp/upfs/${upfId}#formularios`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // Sem clicar em nada nem paginar: a opção distante já está no select.
    await page.getByLabel("Formulário", { exact: true }).click();
    await expect(
      page.getByRole("option", { name: PAGINA_2, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("option", { name: PAGINA_1, exact: true }),
    ).toBeVisible();
  });

  /**
   * Tamanho de página da tabela — `PAGE_SIZE` em `FormulariosTab.tsx`. O stub
   * das duas páginas acima devolve `count: 2`, abaixo disso: a tabela nunca
   * mostra uma segunda página e "sobreviver à paginação" ficava sem prova.
   * Aqui a listagem filtrada devolve mais que uma página de verdade.
   */
  const PAGE_SIZE = 25;
  const TOTAL_FILTRADO = 30;

  /**
   * Como `stubRespostasEmDuasPaginas`, mas a listagem *filtrada* por
   * `formulario_id` devolve `TOTAL_FILTRADO` respostas — duas páginas na
   * tabela. As duas rotas convivem porque o que as separa é a presença do
   * filtro: a varredura do select nunca manda `formulario_id`.
   */
  async function stubComPaginacaoNaTabela(page: import("@playwright/test").Page) {
    await page.route(/\/formularios\/opcoes\/$/, (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ code: "not_found", message: "Não encontrado." }),
      }),
    );

    await page.route(/\/api\/v1\/sgp\/upfs\/\d+\/formularios\/(\?|$)/, async (route) => {
      const params = new URL(route.request().url()).searchParams;
      const pagina = Number(params.get("page") ?? "1");

      if (params.get("formulario_id") === String(ID_PAGINA_2)) {
        const nesta = pagina === 1 ? PAGE_SIZE : TOTAL_FILTRADO - PAGE_SIZE;
        const primeiro = 1000 + (pagina - 1) * PAGE_SIZE;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: TOTAL_FILTRADO,
            next: pagina === 1 ? "http://x/?page=2" : null,
            previous: pagina === 1 ? null : "http://x/?page=1",
            results: Array.from({ length: nesta }, (_, i) =>
              resposta(primeiro + i, ID_PAGINA_2, PAGINA_2),
            ),
          }),
        });
      }

      // Sem filtro: as mesmas duas páginas que a varredura do select percorre,
      // com o formulário alvo só na segunda.
      const page1 = pagina === 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 2,
          next: page1 ? "http://x/?page=2" : null,
          previous: null,
          results: page1
            ? [resposta(1, 55, PAGINA_1)]
            : [resposta(2, ID_PAGINA_2, PAGINA_2)],
        }),
      });
    });
  }

  test("a seleção do formulário sobrevive à troca de página da tabela", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await stubComPaginacaoNaTabela(page);

    await page.goto(`/sgp/upfs/${upfId}#formularios`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.getByLabel("Formulário", { exact: true }).click();
    await page.getByRole("option", { name: PAGINA_2, exact: true }).click();

    // Primeira página do resultado filtrado: a tabela enche e sobra gente.
    const linhas = page.getByTestId(/^formulario-row-/);
    await expect(linhas).toHaveCount(PAGE_SIZE);

    // A requisição da página 2 tem de levar o filtro junto — se a troca de
    // página o descartasse, voltariam as respostas de todos os formulários.
    const requisicaoPagina2 = page.waitForRequest((r) => {
      const u = new URL(r.url());
      return (
        u.pathname.endsWith(`/upfs/${upfId}/formularios/`) &&
        u.searchParams.get("page") === "2" &&
        u.searchParams.get("page_size") === String(PAGE_SIZE)
      );
    });
    await page.getByRole("button", { name: "Próxima página" }).click();
    const enviado = new URL((await requisicaoPagina2).url()).searchParams;
    expect(enviado.get("formulario_id")).toBe(String(ID_PAGINA_2));

    // Chegou na página 2 e a seleção continua na tela e na URL.
    await expect(linhas).toHaveCount(TOTAL_FILTRADO - PAGE_SIZE);
    await expect(page.getByLabel("Formulário", { exact: true })).toContainText(
      PAGINA_2,
    );
    await expect(page).toHaveURL(new RegExp(`formulario_id=${ID_PAGINA_2}`));

    // E a opção segue no select depois de paginar: as opções não podem encolher
    // para o que a página corrente devolveu — foi justamente esse o bug.
    await page.getByLabel("Formulário", { exact: true }).click();
    await expect(
      page.getByRole("option", { name: PAGINA_2, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("option", { name: PAGINA_1, exact: true }),
    ).toBeVisible();
  });

  test("a seleção do formulário distante sobrevive ao reload e à reabertura da aba", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await stubRespostasEmDuasPaginas(page);

    await page.goto(`/sgp/upfs/${upfId}#formularios`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.getByLabel("Formulário", { exact: true }).click();
    await page.getByRole("option", { name: PAGINA_2, exact: true }).click();

    // Vai para a URL...
    await expect(page).toHaveURL(new RegExp(`formulario_id=${ID_PAGINA_2}`));

    // ...sobrevive ao reload...
    await page.reload();
    await expect(page.getByLabel("Formulário", { exact: true })).toContainText(
      PAGINA_2,
    );
    await expect(page).toHaveURL(new RegExp(`formulario_id=${ID_PAGINA_2}`));

    // ...e à saída e volta da aba.
    await page.getByRole("tab", { name: "Membros" }).click();
    await page.getByRole("tab", { name: "Formulários" }).click();
    await expect(page.getByLabel("Formulário", { exact: true })).toContainText(
      PAGINA_2,
    );
  });
});
