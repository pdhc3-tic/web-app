import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

/**
 * Aba "Formulários" na ficha da UPF (#178) — testa integração da tabela +
 * modal de detalhe (#179) + empty state com CTA (stub, wire em #181) +
 * filtros (#180: formulário, período, respondente + URL sync).
 *
 * O `seed_demo` passou a criar `FormResponse` (ver `_form_responses`), então os
 * cenários de filtro saíram do `.fixme` e rodam contra o banco de demo — ver o
 * describe "SGP — Filtros da aba Formulários". Seguem em `.fixme` apenas os
 * dois cenários que dependem de `FormularioSGF` publicado no seed, que é outro
 * contrato (BE-18) e não faz parte da #180.
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
      // O seed já cria FormResponse, então o `.fixme` aqui é só de escopo:
      // ordenação e modal são critério da #178/#179, não da #180. Ao retomar,
      // ancorar a assertion do modal em `respostas_json` conhecido — o seed
      // grava `atividade_principal` no formulário recente.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);

      const linhas = page.locator('tr[data-testid^="formulario-row-"]');
      await expect(linhas.first()).toBeVisible();
      await linhas.first().click();

      const modal = page.getByTestId("resposta-formulario-slideover");
      await expect(modal).toBeVisible();
    },
  );
});

/**
 * Filtros da aba (#180) contra o dado real do `seed_demo._form_responses`, que
 * concentra as respostas na UPF de menor id — a mesma que `primeiroUpfId()`
 * devolve. O contrato do seed, que é o que estes testes assumem:
 *
 * - `Diagnóstico produtivo` (v1.0): 28 respostas, **uma por dia**, do dia do
 *   seed até 27 dias antes, com `respondente` alternando por paridade do dia —
 *   "Técnico de Campo" nos pares, anônima (`NULL`) nos ímpares;
 * - `Perfil socioeconômico da família` (v2.0): 3 respostas, 90/100/110 dias
 *   antes — todas com respondente.
 *
 * Nada aqui é ancorado no relógio da máquina que roda a suíte. O seed pode ter
 * rodado dias antes, e "hoje" deslocaria a janela para fora da faixa coberta;
 * por isso o dia 0 é **lido da tabela** (`diaZeroDoSeed`), não calculado. Os
 * únicos números fixos são os que independem da data: as 3 respostas do
 * segundo formulário e o intervalo de 90 dias que separa os dois conjuntos.
 */
test.describe("SGP — Filtros da aba Formulários", () => {
  test.use({ storageState: storageStatePath("ugp") });

  /** Nomes, id e versão de `FORMULARIOS_DEMO`, em `seed_demo.py`. */
  const FORM_RECENTE = "Diagnóstico produtivo";
  const FORM_ANTIGO = "Perfil socioeconômico da família";
  const ID_FORM_ANTIGO = 2102;
  const VERSAO_FORM_ANTIGO = "2.0";

  /** Quantas respostas o seed cria para `FORM_ANTIGO`. Independe da data. */
  const RESPOSTAS_FORM_ANTIGO = 3;

  /** Tamanho da janela usada nos testes de período. */
  const DIAS_DA_JANELA = 7;

  /** Respondente gravado pelo seed. O filtro do backend é `icontains`. */
  const RESPONDENTE_SEED = "Técnico de Campo";

  /** Rótulo que a tabela usa quando `respondente` vem `NULL` (#178). */
  const ROTULO_ANONIMO = "Anônimo";

  /** `PAGE_SIZE` da aba — a listagem sem filtro enche a página. */
  const PAGE_SIZE = 25;

  /** Colunas da tabela, na ordem em que `FormulariosTab.Tabela` as monta. */
  const COL = { formulario: 0, versao: 1, data: 2, respondente: 3 } as const;

  function linhas(page: Page) {
    return page.locator('tr[data-testid^="formulario-row-"]');
  }

  /** Texto de uma coluna em todas as linhas visíveis. */
  function coluna(page: Page, indice: number): Promise<string[]> {
    return linhas(page).locator(`td:nth-child(${indice + 1})`).allInnerTexts();
  }

  /**
   * Converte o `dd/MM/yyyy` que a coluna Data exibe (`formatDate`) de volta
   * para `YYYY-MM-DD`, que é o formato do input date e do parâmetro da API.
   */
  function isoDaCelula(texto: string): string {
    const [dia, mes, ano] = texto.trim().split("/");
    return `${ano}-${mes}-${dia}`;
  }

  /**
   * Desloca um `YYYY-MM-DD` em `dias`, sem passar por `toISOString()`.
   *
   * O `toISOString()` converte para UTC e, a oeste de Greenwich, devolve o dia
   * seguinte a partir das 21h — foi exatamente o bug corrigido na #157. A data
   * é construída ao meio-dia justamente para nenhum ajuste de fuso atravessar
   * a fronteira do dia.
   */
  function somaDias(iso: string, dias: number): string {
    const [ano, mes, dia] = iso.split("-").map(Number);
    const d = new Date(ano, mes - 1, dia, 12);
    d.setDate(d.getDate() + dias);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  /**
   * Data da resposta mais recente da UPF — o "dia 0" do seed.
   *
   * A listagem vem ordenada por `-data_preenchimento` (`FormResponse.Meta`),
   * então a primeira linha da primeira página é sempre a mais nova. Toda janela
   * destes testes é relativa a ela, e não a `new Date()`: o seed pode ter
   * rodado dias antes da suíte, e aí uma janela ancorada em "hoje" cairia fora
   * da faixa que ele cobre.
   */
  async function diaZeroDoSeed(page: Page): Promise<string> {
    const celula = linhas(page).first().locator("td").nth(COL.data);
    await expect(celula).toHaveText(/^\d{2}\/\d{2}\/\d{4}$/);
    return isoDaCelula(await celula.innerText());
  }

  /**
   * Promessa da listagem que carrega exatamente os pares de `esperado` na
   * query. Precisa ser criada ANTES da interação: cada mudança de filtro
   * dispara um fetch, e ler a tabela logo após digitar pegaria as linhas do
   * resultado anterior, ainda em tela.
   */
  function aguardaListagem(page: Page, esperado: Record<string, string>) {
    return page.waitForResponse((r) => {
      const url = new URL(r.url());
      if (!url.pathname.endsWith("/formularios/")) return false;
      return Object.entries(esperado).every(
        ([chave, valor]) => url.searchParams.get(chave) === valor,
      );
    });
  }

  /**
   * Conta as linhas depois que a tabela terminou de refletir o novo filtro.
   *
   * `waitForResponse` resolve quando a resposta chega à rede, mas o React só
   * troca as linhas no render seguinte — um `count()` imediato leria ainda o
   * resultado anterior. O `expect.poll` repete a leitura até o predicado
   * passar, e é isso que serve de sinal de que o render veio.
   */
  async function contarJaRenderizado(
    page: Page,
    predicado: (n: number) => boolean,
  ): Promise<number> {
    await expect
      .poll(async () => predicado(await linhas(page).count()))
      .toBe(true);
    return linhas(page).count();
  }

  /** Abre a aba já com a tabela carregada (não o empty state). */
  async function abrirComRespostas(page: Page): Promise<void> {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#formularios`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // A UPF do seed tem 31 respostas: a primeira página vem cheia. Serve de
    // linha de base para `contarJaRenderizado` distinguir o antes do depois.
    await expect(linhas(page)).toHaveCount(PAGE_SIZE);
  }

  /**
   * Aplica De/Até e só volta quando a listagem da janela chegou.
   *
   * A ordem importa: "De" tem `max={data_fim}` e "Até" tem `min={data_inicio}`,
   * então mover a janela para trás no tempo exige preencher "De" primeiro
   * (é ele que solta o piso do outro). Todos os chamadores respeitam isso.
   */
  async function aplicarJanela(
    page: Page,
    de: string,
    ate: string,
  ): Promise<void> {
    await page.getByLabel("De", { exact: true }).fill(de);
    const carregou = aguardaListagem(page, { data_inicio: de, data_fim: ate });
    await page.getByLabel("Até", { exact: true }).fill(ate);
    await carregou;
  }

  test("filtro por período restringe as respostas ao intervalo escolhido", async ({
    page,
  }) => {
    await abrirComRespostas(page);
    const dia0 = await diaZeroDoSeed(page);

    // ── Janela recente: os últimos 7 dias do bloco de uma resposta por dia.
    const inicio = somaDias(dia0, -(DIAS_DA_JANELA - 1));
    await aplicarJanela(page, inicio, dia0);

    await expect(page).toHaveURL(
      new RegExp(`data_inicio=${inicio}[^]*data_fim=${dia0}`),
    );

    const naJanela = await contarJaRenderizado(
      page,
      (n) => n > 0 && n <= DIAS_DA_JANELA,
    );

    // O critério, literalmente: nenhuma data fora do intervalo pedido.
    const datas = await coluna(page, COL.data);
    for (const texto of datas) {
      const iso = isoDaCelula(texto);
      expect(iso >= inicio && iso <= dia0).toBe(true);
    }
    // Uma resposta por dia — a janela não pode trazer duas do mesmo dia.
    expect(new Set(datas).size).toBe(naJanela);
    // E só o bloco recente cabe aqui: o antigo está 90 dias atrás.
    for (const nome of await coluna(page, COL.formulario)) {
      expect(nome.trim()).toBe(FORM_RECENTE);
    }

    // ── Janela antiga: cobre SÓ o bloco de 90/100/110 dias atrás. Os 33 dias
    // de folga entre o fim do bloco recente (dia 27) e o começo do antigo
    // (dia 90) são o que torna esta contagem exata, e não uma estimativa.
    await aplicarJanela(page, somaDias(dia0, -120), somaDias(dia0, -60));

    await expect(linhas(page)).toHaveCount(RESPOSTAS_FORM_ANTIGO);
    for (const nome of await coluna(page, COL.formulario)) {
      expect(nome.trim()).toBe(FORM_ANTIGO);
    }
  });

  test("filtro por formulário específico restringe às respostas daquele formulário", async ({
    page,
  }) => {
    await abrirComRespostas(page);

    const carregou = aguardaListagem(page, {
      formulario_id: String(ID_FORM_ANTIGO),
    });
    await page.getByLabel("Formulário", { exact: true }).click();
    await page.getByRole("option", { name: FORM_ANTIGO, exact: true }).click();
    await carregou;

    await expect(page).toHaveURL(new RegExp(`formulario_id=${ID_FORM_ANTIGO}`));

    // As 3 do seed, e só elas — o outro formulário tem 28 e nenhuma pode vazar.
    await expect(linhas(page)).toHaveCount(RESPOSTAS_FORM_ANTIGO);
    for (const nome of await coluna(page, COL.formulario)) {
      expect(nome.trim()).toBe(FORM_ANTIGO);
    }
    for (const versao of await coluna(page, COL.versao)) {
      expect(versao.trim()).toBe(VERSAO_FORM_ANTIGO);
    }
  });

  test("combinar filtro de período + respondente restringe corretamente", async ({
    page,
  }) => {
    await abrirComRespostas(page);
    const dia0 = await diaZeroDoSeed(page);

    const inicio = somaDias(dia0, -(DIAS_DA_JANELA - 1));
    await aplicarJanela(page, inicio, dia0);
    const naJanela = await contarJaRenderizado(
      page,
      (n) => n > 1 && n <= DIAS_DA_JANELA,
    );

    // Soma o respondente à janela já aplicada. `fill` de uma vez (e não tecla a
    // tecla) para o filtro sair num único evento de mudança.
    const carregou = aguardaListagem(page, {
      data_inicio: inicio,
      data_fim: dia0,
      respondente: RESPONDENTE_SEED,
    });
    await page.getByLabel("Respondente", { exact: true }).fill(RESPONDENTE_SEED);
    await carregou;

    await expect(page).toHaveURL(new RegExp(`data_inicio=${inicio}`));
    await expect(page).toHaveURL(new RegExp(`data_fim=${dia0}`));
    await expect(page).toHaveURL(/respondente=T/);

    // O corte é de verdade: o seed alterna o respondente pela paridade do dia,
    // então qualquer janela de dias corridos tem ao menos uma anônima — o
    // resultado combinado é estritamente menor que o da janela sozinha.
    const comRespondente = await contarJaRenderizado(
      page,
      (n) => n > 0 && n < naJanela,
    );
    expect(comRespondente).toBeGreaterThan(0);

    // E os dois filtros valem ao mesmo tempo, não um de cada vez.
    for (const texto of await coluna(page, COL.respondente)) {
      expect(texto.trim()).toBe(RESPONDENTE_SEED);
    }
    for (const texto of await coluna(page, COL.data)) {
      const iso = isoDaCelula(texto);
      expect(iso >= inicio && iso <= dia0).toBe(true);
    }
  });

  /**
   * O subcritério "apenas Anônimas" ficou de fora quando a #180 foi
   * implementada: o `FormResponseFilter` só tinha `respondente__icontains`, e
   * filtrar no cliente quebraria a paginação (uma página de 25 podendo sobrar
   * 3). A PR #214 acrescentou `respondente_isnull` ao backend — é o que este
   * teste exercita, junto da exclusividade entre os dois campos.
   */
  test('"Apenas anônimas" e a busca por respondente particionam a janela', async ({
    page,
  }) => {
    await abrirComRespostas(page);
    const dia0 = await diaZeroDoSeed(page);

    const inicio = somaDias(dia0, -(DIAS_DA_JANELA - 1));
    await aplicarJanela(page, inicio, dia0);
    const naJanela = await contarJaRenderizado(
      page,
      (n) => n > 1 && n <= DIAS_DA_JANELA,
    );

    const carregouAnonimas = aguardaListagem(page, {
      data_inicio: inicio,
      data_fim: dia0,
      respondente_isnull: "true",
    });
    await page.getByTestId("formularios-filtro-anonimas").check();
    await carregouAnonimas;

    // Serializado como "1" na URL (booleano), e o `respondente` sai de lá.
    await expect(page).toHaveURL(/apenas_anonimas=1/);
    await expect(page).not.toHaveURL(/[?&]respondente=/);

    // A busca textual fica travada enquanto isto está ligado: os dois filtros
    // são mutuamente exclusivos, e "Anônimo" é rótulo de tela — não casa com
    // nenhum `icontains` no banco.
    await expect(page.getByLabel("Respondente", { exact: true })).toBeDisabled();

    const anonimas = await contarJaRenderizado(
      page,
      (n) => n > 0 && n < naJanela,
    );
    for (const texto of await coluna(page, COL.respondente)) {
      expect(texto.trim()).toBe(ROTULO_ANONIMO);
    }

    // Complemento exato: na mesma janela, anônimas + identificadas = total.
    // É o que prova que o filtro é `IS NULL`, e não um `icontains` que por
    // acaso não casou com nada.
    const carregouIdentificadas = aguardaListagem(page, {
      data_inicio: inicio,
      data_fim: dia0,
      respondente: RESPONDENTE_SEED,
    });
    await page.getByTestId("formularios-filtro-anonimas").uncheck();
    await page.getByLabel("Respondente", { exact: true }).fill(RESPONDENTE_SEED);
    await carregouIdentificadas;

    await contarJaRenderizado(page, (n) => n === naJanela - anonimas);
  });
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
