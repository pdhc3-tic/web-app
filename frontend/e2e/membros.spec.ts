import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

/**
 * Aba "Membros" na ficha da UPF (#188) e o formulário de cadastro/edição de
 * membro (FE-22), que já existia desde a issue 100.
 *
 * O cenário "com membros" sai do `seed_demo`, que cria um titular + cônjuge +
 * filhos em toda UPF. O cenário vazio NÃO tem como sair do seed: `UPF.titular`
 * é FK obrigatória para um `MembroFamilia` e esse membro aparece na própria
 * listagem — por isso o empty state é exercitado interceptando o GET da lista.
 *
 * O card-resumo da composição familiar (FE-23) sai do endpoint `membros/resumo/`
 * (BE-23). Os cenários de composição conhecida e de UPF sem Titular fixam esse
 * endpoint junto com a listagem — o segundo, de novo, não existe no seed.
 *
 * A asserção do badge do Titular mora aqui, e não num teste de componente,
 * porque o projeto ainda não tem runner de componente (mesma pendência da
 * issue 133). Ao montar o runner, ela pode migrar para `MembrosTab.test.tsx`.
 */

/** Regex do GET da listagem — não pega o detalhe (`/membros/{id}/`). */
const LISTA_MEMBROS = /\/api\/v1\/sgp\/upfs\/\d+\/membros\/(\?|$)/;

/** Regex do GET do resumo agregado da composição familiar (BE-23). */
const RESUMO_MEMBROS = /\/api\/v1\/sgp\/upfs\/\d+\/membros\/resumo\/$/;

/**
 * Prefixo dos membros criados pelos testes. O `limparMembrosDeTeste` apaga por
 * ele no fim da suíte — sem isso cada execução deixaria lixo no banco de demo.
 */
const PREFIXO_TESTE = "E2E Membro";

async function abrirAbaMembros(page: Page, upfId: number): Promise<void> {
  await page.goto(`/sgp/upfs/${upfId}#membros`);
  // Sem isto a aba ainda pode estar sob o skeleton do fetch da própria UPF.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Membros" })).toBeVisible();
  await expect(page.getByTestId("membros-tab")).toBeVisible();
}

/**
 * O painel inteiro do SlideOver. O corpo tem `data-testid`, mas o rodapé com
 * Salvar/Cancelar é irmão dele — este escopo cobre os dois.
 *
 * É seletor de atributo, e não `getByRole("dialog")`, porque o backdrop que
 * envolve o painel é `aria-hidden` e some das buscas por role.
 */
function painelMembro(page: Page): Locator {
  return page.locator('[role="dialog"]');
}

/** Abre o formulário de novo membro pelo botão do cabeçalho da aba. */
async function abrirFormularioNovoMembro(page: Page): Promise<Locator> {
  await page.getByRole("button", { name: "Adicionar membro" }).click();
  const painel = painelMembro(page);
  await expect(painel.getByTestId("membro-slideover")).toHaveAttribute(
    "data-mode",
    "create",
  );
  return painel;
}

/** Escolhe uma opção nos <Select> do design system (combobox custom). */
async function escolherNoSelect(
  painel: Locator,
  label: string,
  opcao: string,
): Promise<void> {
  await painel.getByLabel(label, { exact: true }).click();
  await painel
    .locator('[role="listbox"] li')
    .filter({ hasText: opcao })
    .first()
    .click();
}

/** Chip já selecionado de um MultiSelect (o botão que o remove). */
function chipSelecionado(painel: Locator, rotulo: string): Locator {
  return painel.locator(`[aria-label="Remover ${rotulo}"]`);
}

/** Opção ainda não selecionada de um MultiSelect, dentro do grupo `label`. */
function opcaoDisponivel(
  painel: Locator,
  grupo: string,
  rotulo: string,
): Locator {
  return painel
    .locator(`[role="group"][aria-label="${grupo}"]`)
    .locator("button")
    .filter({ hasText: rotulo });
}

/**
 * CPF válido e novo a cada chamada. O backend valida dígito verificador e
 * exige CPF único global, então um valor fixo quebraria na segunda execução.
 * A base vem do relógio; os dígitos seguem a mesma conta de `isValidCpf`.
 */
function gerarCpfValido(): string {
  const base = String(Date.now()).slice(-9).split("").map(Number);
  const digito = (nums: number[]): number => {
    const peso = nums.length + 1;
    const soma = nums.reduce((acc, n, i) => acc + n * (peso - i), 0);
    const resto = (soma * 10) % 11;
    return resto === 10 ? 0 : resto;
  };
  const d1 = digito(base);
  const d2 = digito([...base, d1]);
  return [...base, d1, d2].join("");
}

/** Data ISO de quem completou exatamente `anos` anos ontem. */
function nascimentoComIdade(anos: number): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  d.setFullYear(d.getFullYear() - anos);
  return d.toISOString().slice(0, 10);
}

/**
 * Apaga os membros criados pelos testes. Exclui titulares por segurança:
 * `UPF.titular` referencia a linha e o delete cru falharia na FK.
 */
function limparMembrosDeTeste(): void {
  execFileSync(
    "docker",
    [
      "exec",
      "db",
      "psql",
      "-U",
      "postgres",
      "-d",
      "app_db",
      "-c",
      `delete from sgp_membrofamilia where nome_completo like '${PREFIXO_TESTE}%' and grau_parentesco <> 'titular';`,
    ],
    { encoding: "utf8", timeout: 30_000 },
  );
}

/**
 * Membro no formato de `MembroListSerializer` — só os campos que a listagem
 * lê precisam ser reais.
 */
function membroFake(
  id: number,
  nome: string,
  parentesco: string,
  parentescoDisplay: string,
): Record<string, unknown> {
  return {
    id,
    nome_completo: nome,
    data_nascimento: null,
    idade: null,
    grau_parentesco: parentesco,
    grau_parentesco_display: parentescoDisplay,
    cpf: "",
    genero: null,
    genero_display: "",
    cor_raca: null,
    cor_raca_display: "",
    criado_em: "2026-01-01T00:00:00Z",
  };
}

/**
 * Fixa listagem e resumo de uma UPF. O resumo tem endpoint próprio (BE-23),
 * então os dois precisam ser interceptados juntos — senão o card mostraria os
 * agregados reais do seed sobre uma listagem falsa.
 */
async function stubComposicao(
  page: Page,
  membros: Record<string, unknown>[],
  resumo: Record<string, unknown>,
): Promise<void> {
  await page.route(RESUMO_MEMBROS, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(resumo),
    });
  });
  await page.route(LISTA_MEMBROS, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(membros),
    });
  });
}

test.describe("SGP — Aba Membros na UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("UPF com membros lista os integrantes com a idade calculada", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await abrirAbaMembros(page, upfId);

    const linhas = page.locator('tr[data-testid^="membro-row-"]');
    await expect(linhas.first()).toBeVisible();
    expect(await linhas.count()).toBeGreaterThan(0);

    // Idade calculada: 3ª coluna (Nome · Parentesco · Idade · …).
    await expect(linhas.first().locator("td").nth(2)).toHaveText(
      /^\d+ anos?$/,
    );

    // Badge do Titular: exatamente um por UPF, e na primeira linha — a tabela
    // ordena o titular no topo.
    const badges = page.getByTestId("membro-badge-titular");
    await expect(badges).toHaveCount(1);
    await expect(linhas.first().getByTestId("membro-badge-titular")).toBeVisible();

    // O card-resumo fala do mesmo conjunto que a tabela mostra: a listagem vem
    // sem paginação (limit=1000), então o total do backend bate com as linhas.
    await expect(page.getByTestId("membros-resumo")).toBeVisible();
    await expect(page.getByTestId("membros-resumo-total")).toHaveText(
      String(await linhas.count()),
    );
    // Toda UPF do seed tem Titular — nada de alerta de Atenção aqui.
    await expect(page.getByTestId("membros-sem-titular-alerta")).toHaveCount(0);

    // Campos sensíveis não podem aparecer na listagem resumida (regra FE-25).
    await expect(page.getByRole("columnheader", { name: "Saúde" })).toHaveCount(0);
    await expect(
      page.getByRole("columnheader", { name: "Cor/Raça" }),
    ).toHaveCount(0);

    // Clique na linha abre o painel do membro (detalhe → botão Editar).
    await linhas.first().click();
    await expect(page.getByTestId("membro-slideover")).toBeVisible();
    await expect(page.getByTestId("membro-slideover")).toHaveAttribute(
      "data-mode",
      "view",
    );
  });

  test("UPF sem membros exibe o card-resumo zerado, o alerta e o CTA para cadastrar o Titular", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // Listagem e resumo fixados juntos: com zero membros o card precisa
    // aparecer assim mesmo — total 0, faixas zeradas e o alerta de Atenção.
    await stubComposicao(page, [], {
      total_membros: 0,
      faixa_etaria: {
        "0-11": 0,
        "12-17": 0,
        "18-59": 0,
        "60+": 0,
        sem_data_nascimento: 0,
      },
      genero: { masculino: 0, feminino: 0, nao_binario: 0, nao_informado: 0 },
      tem_titular: false,
    });

    await abrirAbaMembros(page, upfId);

    // O card não some junto com a lista.
    const card = page.getByTestId("membros-resumo");
    await expect(card).toBeVisible();
    await expect(card.getByTestId("membros-resumo-total")).toHaveText("0");
    for (const faixa of ["0-11", "12-17", "18-59", "60+"]) {
      await expect(card.getByTestId(`membros-resumo-faixa-${faixa}`)).toContainText(
        "0",
      );
    }

    const alerta = page.getByTestId("membros-sem-titular-alerta");
    await expect(alerta).toBeVisible();
    await expect(alerta).toContainText("Esta UPF não tem Titular.");
    // Paleta "Atenção" do design system (--color-warning-bg).
    await expect(alerta).toHaveCSS("background-color", "rgb(255, 248, 225)");

    // Exportar CSV continua atrelado à lista — sem membros não há o que gerar.
    await expect(page.getByTestId("membros-exportar-csv")).toHaveCount(0);

    // O estado vazio e o CTA ficam logo abaixo do card.
    await expect(
      page.getByText("Nenhum membro cadastrado ainda.", { exact: true }),
    ).toBeVisible();

    const cta = page.getByTestId("membros-adicionar-primeiro");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveText(/Adicionar primeiro membro/i);

    // O primeiro membro precisa ser o Titular — o formulário já abre assim.
    await cta.click();
    const painel = page.getByTestId("membro-slideover");
    await expect(painel).toBeVisible();
    await expect(painel).toHaveAttribute("data-mode", "create");
    await expect(painel.getByLabel("Parentesco")).toHaveValue("titular");
  });

  test("card-resumo exibe os totais de uma composição familiar conhecida", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    await stubComposicao(
      page,
      [
        membroFake(9001, `${PREFIXO_TESTE} Titular`, "titular", "Titular"),
        membroFake(9002, `${PREFIXO_TESTE} Cônjuge`, "conjuge", "Cônjuge"),
        membroFake(9003, `${PREFIXO_TESTE} Filha`, "filho", "Filho(a)"),
        membroFake(9004, `${PREFIXO_TESTE} Filho`, "filho", "Filho(a)"),
        membroFake(9005, `${PREFIXO_TESTE} Avó`, "avo", "Avô(ó)"),
        membroFake(9006, `${PREFIXO_TESTE} Neto`, "neto", "Neto(a)"),
      ],
      {
        total_membros: 6,
        faixa_etaria: {
          "0-11": 2,
          "12-17": 1,
          "18-59": 2,
          "60+": 1,
          sem_data_nascimento: 0,
        },
        genero: { masculino: 3, feminino: 3, nao_binario: 0, nao_informado: 0 },
        tem_titular: true,
      },
    );

    await abrirAbaMembros(page, upfId);

    const card = page.getByTestId("membros-resumo");
    await expect(card).toBeVisible();
    await expect(card.getByTestId("membros-resumo-total")).toHaveText("6");

    // Uma pastilha por faixa, inclusive as zeradas — a soma fecha com o total.
    await expect(card.getByTestId("membros-resumo-faixa-0-11")).toContainText(
      "2",
    );
    await expect(card.getByTestId("membros-resumo-faixa-12-17")).toContainText(
      "1",
    );
    await expect(card.getByTestId("membros-resumo-faixa-18-59")).toContainText(
      "2",
    );
    await expect(card.getByTestId("membros-resumo-faixa-60+")).toContainText(
      "1",
    );
    await expect(
      card.getByTestId("membros-resumo-faixa-sem_data_nascimento"),
    ).toContainText("0");
    await expect(card.getByText("60 anos ou mais")).toBeVisible();

    await expect(page.getByTestId("membros-sem-titular-alerta")).toHaveCount(0);
  });

  test("UPF sem Titular exibe o alerta de Atenção no card-resumo", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // Cenário que o seed não produz: `UPF.titular` é FK obrigatória, então
    // nenhuma UPF real fica sem Titular. Listagem e resumo vão fixados juntos.
    await stubComposicao(
      page,
      [
        membroFake(9101, `${PREFIXO_TESTE} Sem titular`, "filho", "Filho(a)"),
        membroFake(9102, `${PREFIXO_TESTE} Irmã`, "irmao", "Irmão(ã)"),
      ],
      {
        total_membros: 2,
        faixa_etaria: {
          "0-11": 0,
          "12-17": 1,
          "18-59": 1,
          "60+": 0,
          sem_data_nascimento: 0,
        },
        genero: { masculino: 1, feminino: 1, nao_binario: 0, nao_informado: 0 },
        tem_titular: false,
      },
    );

    await abrirAbaMembros(page, upfId);

    const alerta = page.getByTestId("membros-sem-titular-alerta");
    await expect(alerta).toBeVisible();
    await expect(alerta).toContainText("Esta UPF não tem Titular.");
    // Paleta "Atenção" do design system (--color-warning-bg).
    await expect(alerta).toHaveCSS("background-color", "rgb(255, 248, 225)");

    // E nenhuma linha da tabela pode ostentar o badge do Titular.
    await expect(page.getByTestId("membro-badge-titular")).toHaveCount(0);
  });
});

/**
 * Formulário de cadastro/edição de membro (FE-22).
 *
 * O teste da exclusividade de "Nenhuma" em Saúde é o "teste de componente" que
 * a issue pede: o projeto não tem runner de componente (pendência da issue 133)
 * e o MultiSelect não está exposto no /styleguide, então ele roda aqui — sem
 * salvar nada, exercitando só a lógica de seleção do próprio componente.
 */
test.describe("SGP — Formulário de membro", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.afterAll(() => {
    limparMembrosDeTeste();
  });

  test("preenche o formulário completo e salva — o membro aparece na aba", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    const nome = `${PREFIXO_TESTE} ${Date.now()}`;
    const cpf = gerarCpfValido();
    // A listagem esconde o miolo do CPF (maskCpf): "123.***.***-09".
    const cpfMascarado = `${cpf.slice(0, 3)}.***.***-${cpf.slice(9)}`;

    await abrirAbaMembros(page, upfId);
    const painel = await abrirFormularioNovoMembro(page);

    await painel.getByLabel("Nome completo").fill(nome);
    await painel.getByLabel("Parentesco").selectOption("filho");
    await painel.getByLabel("Data de nascimento").fill(nascimentoComIdade(20));
    await escolherNoSelect(painel, "Gênero", "Feminino");
    await escolherNoSelect(painel, "Cor/Raça", "Parda");
    await painel.getByLabel("CPF").fill(cpf);
    await painel.getByLabel("NIS").fill("12345678901");
    await painel.getByLabel("CAF").fill("CAF123456");

    // "Médio incompleto" tem vínculo escolar — só então o campo Escola existe.
    await expect(painel.getByLabel("Escola", { exact: true })).toHaveCount(0);
    await escolherNoSelect(painel, "Escolaridade", "Médio incompleto");
    await painel.getByLabel("Escola", { exact: true }).fill("Escola Estadual E2E");

    await opcaoDisponivel(painel, "Saúde", "Nenhuma").click();
    await opcaoDisponivel(painel, "Seguridade social", "Bolsa Família").click();

    await painel.locator('button:has-text("Salvar")').click();

    await expect(page.getByText("Membro adicionado.")).toBeVisible();

    const linha = page
      .locator('tr[data-testid^="membro-row-"]')
      .filter({ hasText: nome });
    await expect(linha).toHaveCount(1);
    await expect(linha.locator("td").nth(1)).toHaveText("Filho(a)");
    await expect(linha.locator("td").nth(2)).toHaveText("20 anos");
    await expect(linha.locator("td").nth(3)).toHaveText("Feminino");
    await expect(linha.locator("td").nth(4)).toHaveText(cpfMascarado);
  });

  test("CPF com dígito inválido bloqueia o submit antes de chamar o backend", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // Contador de POSTs para o endpoint de membros: o critério é que a
    // validação aconteça ANTES de qualquer request.
    let posts = 0;
    page.on("request", (req) => {
      if (req.method() === "POST" && /\/membros\/$/.test(req.url())) posts++;
    });

    await abrirAbaMembros(page, upfId);
    const painel = await abrirFormularioNovoMembro(page);

    await painel.getByLabel("Nome completo").fill(`${PREFIXO_TESTE} CPF`);
    await painel.getByLabel("Parentesco").selectOption("filho");
    // 123.456.789-09 seria válido; o segundo dígito aqui está trocado.
    await painel.getByLabel("CPF").fill("12345678900");

    await painel.locator('button:has-text("Salvar")').click();

    await expect(painel.getByText("CPF inválido.")).toBeVisible();
    expect(posts, "o submit não pode chamar o backend").toBe(0);
  });

  test("segundo Titular exibe a mensagem de erro do backend", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // A tela previne o caso desabilitando a opção "Titular" quando já existe
    // um. Zerar a listagem reproduz a lista desatualizada — exatamente a
    // corrida que a guarda do backend (BE-22) existe para pegar — e libera a
    // opção. O POST segue para o backend de verdade.
    await page.route(LISTA_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });

    await abrirAbaMembros(page, upfId);
    await page.getByTestId("membros-adicionar-primeiro").click();

    const painel = painelMembro(page);
    await expect(painel.getByLabel("Parentesco")).toHaveValue("titular");
    await painel.getByLabel("Nome completo").fill(`${PREFIXO_TESTE} Titular`);

    await painel.locator('button:has-text("Salvar")').click();

    await expect(
      painel.getByText("Já existe um titular cadastrado para esta UPF"),
    ).toBeVisible();
  });

  test('"Nenhuma" em Saúde desmarca as demais opções, e vice-versa', async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await abrirAbaMembros(page, upfId);
    const painel = await abrirFormularioNovoMembro(page);

    await opcaoDisponivel(painel, "Saúde", "Diabetes").click();
    await opcaoDisponivel(painel, "Saúde", "Hipertensão").click();
    await expect(chipSelecionado(painel, "Diabetes")).toBeVisible();
    await expect(chipSelecionado(painel, "Hipertensão")).toBeVisible();

    // "Nenhuma" limpa as demais.
    await opcaoDisponivel(painel, "Saúde", "Nenhuma").click();
    await expect(chipSelecionado(painel, "Nenhuma")).toBeVisible();
    await expect(chipSelecionado(painel, "Diabetes")).toHaveCount(0);
    await expect(chipSelecionado(painel, "Hipertensão")).toHaveCount(0);

    // E qualquer outra opção descarta "Nenhuma".
    await opcaoDisponivel(painel, "Saúde", "Diabetes").click();
    await expect(chipSelecionado(painel, "Diabetes")).toBeVisible();
    await expect(chipSelecionado(painel, "Nenhuma")).toHaveCount(0);
  });
});

/**
 * Ordem entre a listagem e o resumo (#190, item 5 do review).
 *
 * As duas requisições são paralelas, e o resumo (BE-23) é a fonte da verdade
 * sobre o Titular. Enquanto ele não responde, o alerta não pode ser afirmado a
 * partir da listagem — o que faria o aviso piscar e, se as fontes divergissem,
 * aparecer e sumir na transição.
 *
 * O atraso é aplicado no route handler, não com `waitForTimeout` no teste: a
 * asserção acontece com a resposta comprovadamente ainda em voo.
 */
test.describe("SGP — Card de composição espera o resumo", () => {
  test.use({ storageState: storageStatePath("ugp") });

  const ATRASO_MS = 2500;

  function resumoFake(temTitular: boolean) {
    return {
      total_membros: 2,
      faixa_etaria: {
        "0-11": 0,
        "12-17": 1,
        "18-59": 1,
        "60+": 0,
        sem_data_nascimento: 0,
      },
      genero: { masculino: 1, feminino: 1, nao_binario: 0, nao_informado: 0 },
      tem_titular: temTitular,
    };
  }

  /** Listagem imediata (sem Titular) + resumo atrasado com `temTitular`. */
  async function stubResumoAtrasado(
    page: Page,
    temTitular: boolean,
  ): Promise<void> {
    await page.route(LISTA_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          membroFake(9201, `${PREFIXO_TESTE} Filha`, "filho", "Filho(a)"),
          membroFake(9202, `${PREFIXO_TESTE} Irmã`, "irmao", "Irmão(ã)"),
        ]),
      });
    });

    await page.route(RESUMO_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await new Promise((r) => setTimeout(r, ATRASO_MS));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(resumoFake(temTitular)),
      });
    });
  }

  test("o alerta não aparece enquanto o resumo está em voo, e surge quando tem_titular=false", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    // A listagem não tem Titular: fosse ela a fonte, o alerta apareceria já.
    await stubResumoAtrasado(page, false);

    await abrirAbaMembros(page, upfId);

    // Com a listagem já pintada e o resumo ainda pendente, o alerta tem de
    // estar ausente — é a asserção que o item 5 pede.
    await expect(page.getByTestId("membro-badge-titular")).toHaveCount(0);
    await expect(page.getByTestId("membros-sem-titular-alerta")).toHaveCount(0);

    // E só depois da resposta ele entra.
    await expect(page.getByTestId("membros-sem-titular-alerta")).toBeVisible({
      timeout: ATRASO_MS * 3,
    });
    await expect(page.getByTestId("membros-resumo-total")).toHaveText("2");
  });

  /**
   * Revalidação (item 5 do 2º review): salvar ou remover membro dispara um novo
   * GET do resumo, e o resumo anterior segue em memória durante essa consulta.
   * Ele descreve o estado *antes* da alteração — afirmar o alerta a partir dele
   * é afirmar por antecipação, do mesmo jeito que derivá-lo da listagem era.
   *
   * O cenário abaixo é o que distingue as duas implementações: o alerta está na
   * tela quando a remoção começa. Sem a supressão durante `resumoLoading`, ele
   * continua lá até a resposta chegar; com ela, sai assim que a consulta parte.
   */
  test("na revalidação após remover, o alerta sai da tela até o novo resumo chegar", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    let resumoEmVoo!: () => void;
    const segundaChamadaPartiu = new Promise<void>((r) => {
      resumoEmVoo = r;
    });

    await page.route(LISTA_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          membroFake(9301, `${PREFIXO_TESTE} Filha`, "filho", "Filho(a)"),
          membroFake(9302, `${PREFIXO_TESTE} Irmã`, "irmao", "Irmão(ã)"),
        ]),
      });
    });

    // 1ª resposta: imediata e sem Titular (o alerta entra na tela).
    // 2ª: atrasada e com Titular — é durante esse intervalo que a asserção cai.
    let chamadas = 0;
    await page.route(RESUMO_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      chamadas += 1;
      if (chamadas === 1) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(resumoFake(false)),
        });
      }
      resumoEmVoo();
      await new Promise((r) => setTimeout(r, ATRASO_MS));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...resumoFake(true), total_membros: 1 }),
      });
    });

    await page.route(/\/api\/v1\/sgp\/upfs\/\d+\/membros\/\d+\/$/, async (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      await route.fulfill({ status: 204, body: "" });
    });

    await abrirAbaMembros(page, upfId);

    const alerta = page.getByTestId("membros-sem-titular-alerta");
    await expect(alerta).toBeVisible();
    await expect(page.getByTestId("membros-resumo-total")).toHaveText("2");

    await page
      .getByTestId("membro-row-9302")
      .getByRole("button", { name: "Remover" })
      .click();
    // `:has-text` e não `getByRole(name)`: o rodapé do SlideOver põe o rótulo
    // num <span> interno e o nome acessível do <button> sai vazio — mesmo
    // motivo pelo qual os testes do formulário clicam em "Salvar" assim.
    await painelMembro(page).locator('button:has-text("Confirmar")').click();

    // Com o GET comprovadamente em voo — e ainda faltando ATRASO_MS para
    // responder —, o alerta não pode estar afirmando o resumo antigo.
    //
    // Timeout curto de propósito: com o retry padrão de 5s a asserção passaria
    // pela porta dos fundos, esperando a resposta chegar e o alerta sumir por
    // outro motivo. Ele precisa já estar fora quando a consulta parte.
    await segundaChamadaPartiu;
    await expect(alerta).toHaveCount(0, { timeout: 1000 });

    // Os números anteriores seguem visíveis durante a revalidação: some o que
    // é afirmação (o alerta), não o conteúdo já conferido.
    await expect(page.getByTestId("membros-resumo-total")).toHaveText("2");
    await expect(page.getByTestId("membros-resumo")).toHaveAttribute(
      "aria-busy",
      "true",
    );

    // E, chegada a resposta, o alerta continua fora — agora porque o resumo diz
    // que há Titular, e não porque ninguém sabe ainda.
    await expect(page.getByTestId("membros-resumo-total")).toHaveText("1", {
      timeout: ATRASO_MS * 3,
    });
    await expect(alerta).toHaveCount(0);
    await expect(page.getByTestId("membros-resumo")).not.toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  test("com tem_titular=true o alerta nunca aparece, nem antes nem depois", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    // Mesma listagem sem Titular; o resumo diz que existe. Vence o resumo.
    await stubResumoAtrasado(page, true);

    await abrirAbaMembros(page, upfId);

    await expect(page.getByTestId("membros-sem-titular-alerta")).toHaveCount(0);

    // Espera o resumo chegar (o total só aparece com ele) e reconfere.
    await expect(page.getByTestId("membros-resumo-total")).toHaveText("2", {
      timeout: ATRASO_MS * 3,
    });
    await expect(page.getByTestId("membros-sem-titular-alerta")).toHaveCount(0);
  });
});

// ─── Exportação CSV dos membros (#191) ───────────────────────────────────────

/** GET do arquivo. Não colide com LISTA_MEMBROS, que exige `?` ou fim de path. */
// ─── #192: exibição condicional de Saúde e Cor/Raça ─────────────────────────

/** GET/PATCH do detalhe de um membro. Não casa `resumo/` nem `exportar/`. */
const DETALHE_MEMBRO = /\/api\/v1\/sgp\/upfs\/\d+\/membros\/\d+\/$/;

/** Id do membro fixado nos cenários abaixo. */
const ID_MEMBRO = 9001;

/**
 * Detalhe completo de um membro, com os dois campos sensíveis presentes.
 * Os cenários "sem permissão" partem daqui e **removem as chaves** — é a
 * ausência, e não um valor vazio, que o frontend lê como "não pode ver".
 */
function detalheFake(): Record<string, unknown> {
  return {
    id: ID_MEMBRO,
    upf: 1,
    nome_completo: "Joana Ferreira da Mata",
    data_nascimento: "1979-04-12",
    idade: 47,
    cpf: "52998224725",
    rg: "",
    nis: "12345678901",
    caf: "CAF-001",
    grau_parentesco: "titular",
    grau_parentesco_display: "Titular",
    genero: 2,
    genero_display: "Feminino",
    cor_raca: 3,
    cor_raca_display: "Parda",
    escola: "",
    seguridade_social: ["bolsa_familia"],
    saude: ["diabetes", "hipertensao"],
    escolaridade: 2,
    escolaridade_display: "Fundamental incompleto",
    criado_por: 1,
    criado_em: "2026-01-01T00:00:00Z",
    atualizado_em: "2026-01-01T00:00:00Z",
  };
}

/** O mesmo membro como item de listagem. */
function listaFake(): Record<string, unknown> {
  const d = detalheFake();
  return {
    id: d.id,
    nome_completo: d.nome_completo,
    data_nascimento: d.data_nascimento,
    idade: d.idade,
    grau_parentesco: d.grau_parentesco,
    grau_parentesco_display: d.grau_parentesco_display,
    cpf: d.cpf,
    genero: d.genero,
    genero_display: d.genero_display,
    cor_raca: d.cor_raca,
    cor_raca_display: d.cor_raca_display,
    criado_em: d.criado_em,
  };
}

/** Devolve o objeto sem as chaves pedidas — o que BE-25 faz na resposta. */
function sem(
  objeto: Record<string, unknown>,
  ...chaves: string[]
): Record<string, unknown> {
  const copia = { ...objeto };
  for (const chave of chaves) delete copia[chave];
  return copia;
}

/** Chaves sensíveis que o backend omite por perfil (BE-25/#187). */
const CHAVES_SENSIVEIS = ["cor_raca", "cor_raca_display", "saude"];

/**
 * Fixa listagem, resumo e detalhe do mesmo membro. `PATCH` no detalhe é
 * devolvido com eco do corpo, para o fluxo de salvar completar sem tocar o
 * banco de demo.
 */
async function stubMembroUnico(
  page: Page,
  lista: Record<string, unknown>,
  detalhe: Record<string, unknown>,
): Promise<void> {
  await stubComposicao(page, [lista], {
    total_membros: 1,
    faixa_etaria: {
      "0-11": 0,
      "12-17": 0,
      "18-59": 1,
      "60+": 0,
      sem_data_nascimento: 0,
    },
    genero: { masculino: 0, feminino: 1, nao_binario: 0, nao_informado: 0 },
    tem_titular: true,
  });
  await page.route(DETALHE_MEMBRO, async (route) => {
    const metodo = route.request().method();
    if (metodo === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(detalhe),
      });
    }
    if (metodo === "PATCH") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...detalhe,
          ...(route.request().postDataJSON() as Record<string, unknown>),
        }),
      });
    }
    return route.fallback();
  });
}

/** O `<dt>` de um rótulo dentro do `DefinitionList` do modo view. */
function rotuloNoDetalhe(painel: Locator, rotulo: string): Locator {
  return painel.locator("dt").filter({ hasText: new RegExp(`^${rotulo}$`) });
}

/** Abre o painel do único membro fixado, já no modo pedido. */
async function abrirPainelDoMembro(
  page: Page,
  modo: "view" | "edit",
): Promise<Locator> {
  await abrirAbaMembros(page, primeiroUpfId());
  await page.locator(`tr[data-testid="membro-row-${ID_MEMBRO}"]`).click();

  const painel = painelMembro(page);
  await expect(painel.getByTestId("membro-slideover")).toHaveAttribute(
    "data-mode",
    "view",
  );
  // O painel abre antes do GET do detalhe voltar; sem esperar por um campo do
  // detalhe, as asserções de ausência passariam contra um painel ainda vazio.
  await expect(rotuloNoDetalhe(painel, "Gênero")).toBeVisible();

  if (modo === "edit") {
    await painel.getByRole("button", { name: "Editar" }).click();
    await expect(painel.getByTestId("membro-slideover")).toHaveAttribute(
      "data-mode",
      "edit",
    );
  }
  return painel;
}

/**
 * Exibição condicional de Saúde e Cor/Raça (#192).
 *
 * O critério é o **sinal**: o backend (BE-25/#187) omite as chaves da resposta
 * para quem não tem permissão, e o frontend não renderiza o campo — sem
 * placeholder, sem aviso de "sem acesso". Ausência ≠ valor vazio, e o par de
 * cenários abaixo prova justamente essa diferença: com a chave presente e
 * vazia o rótulo aparece com "—"; sem a chave, o rótulo não existe.
 *
 * Os cenários fixam a resposta com `page.route` por dois motivos, e não por
 * conveniência:
 *
 * 1. o projeto não tem runner de teste de componente (mesma pendência que já
 *    fez a asserção do badge do Titular morar neste arquivo);
 * 2. **não existe perfil capaz de exercitar o caminho "sem permissão" em
 *    runtime.** `UPF_ACCESS_ROLES` (`apps/sgp/views/__init__.py`) e
 *    `SENSITIVE_FIELD_ROLES` (`apps/core/sensitive_fields.py`) são hoje o mesmo
 *    conjunto — quem não lê os campos sensíveis não entra no módulo SGP e
 *    recebe "Você não tem acesso ao módulo SGP" antes de chegar à ficha. Está
 *    registrado no item 6 de `docs/pendencias-backend-sprint-9.md`; enquanto as
 *    duas matrizes coincidirem, o stub é o único caminho. Quando divergirem,
 *    estes testes trocam o `page.route` por um `storageState` do perfil sem
 *    permissão e passam a valer como E2E de ponta a ponta.
 *
 * Listagem e exportação, as outras duas superfícies citadas no critério, já são
 * cobertas neste arquivo: "UPF com membros lista os integrantes…" garante que a
 * tabela nunca tem as colunas, e "arquivo sem a coluna de Saúde desce como
 * veio…" cobre o CSV.
 */
test.describe("SGP — Campos sensíveis por perfil", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("sem as chaves na resposta, o detalhe não mostra Saúde nem Cor/Raça", async ({
    page,
  }) => {
    await stubMembroUnico(
      page,
      sem(listaFake(), ...CHAVES_SENSIVEIS),
      sem(detalheFake(), ...CHAVES_SENSIVEIS),
    );
    const painel = await abrirPainelDoMembro(page, "view");

    await expect(rotuloNoDetalhe(painel, "Cor/Raça")).toHaveCount(0);
    await expect(rotuloNoDetalhe(painel, "Saúde")).toHaveCount(0);

    // Nem o valor, nem qualquer pista de que o dado existe: o critério proíbe
    // placeholder e aviso de permissão.
    await expect(painel.getByText("Parda")).toHaveCount(0);
    await expect(painel.getByText(/sem permissão|sem acesso|oculto/i)).toHaveCount(0);

    // E o resto do painel continua inteiro — a ausência é cirúrgica.
    await expect(rotuloNoDetalhe(painel, "Gênero")).toBeVisible();
    await expect(rotuloNoDetalhe(painel, "Seguridade")).toBeVisible();
  });

  test("com as chaves presentes e vazias, os rótulos continuam na tela", async ({
    page,
  }) => {
    // Contraprova do critério "ausência do campo, e não valor vazio": aqui o
    // perfil TEM permissão e o membro é que não tem dado preenchido. O rótulo
    // precisa aparecer, com o travessão do DefinitionList.
    await stubMembroUnico(
      page,
      { ...listaFake(), cor_raca: null, cor_raca_display: "" },
      { ...detalheFake(), cor_raca: null, cor_raca_display: "", saude: [] },
    );
    const painel = await abrirPainelDoMembro(page, "view");

    await expect(rotuloNoDetalhe(painel, "Cor/Raça")).toBeVisible();
    await expect(rotuloNoDetalhe(painel, "Saúde")).toBeVisible();
  });

  test("no formulário de edição os campos somem e o PATCH não os envia", async ({
    page,
  }) => {
    await stubMembroUnico(
      page,
      sem(listaFake(), ...CHAVES_SENSIVEIS),
      sem(detalheFake(), ...CHAVES_SENSIVEIS),
    );
    const painel = await abrirPainelDoMembro(page, "edit");

    // Os controles não existem — nem o Select de Cor/Raça, nem o grupo de Saúde.
    await expect(painel.getByLabel("Cor/Raça", { exact: true })).toHaveCount(0);
    await expect(
      painel.locator('[role="group"][aria-label="Saúde"]'),
    ).toHaveCount(0);
    // Os vizinhos imediatos de cada um seguem lá, provando que o formulário
    // renderizou e só os dois sumiram.
    await expect(painel.getByLabel("Gênero", { exact: true })).toBeVisible();
    await expect(
      painel.locator('[role="group"][aria-label="Seguridade social"]'),
    ).toBeVisible();

    // Salvar não pode reintroduzir os campos pelo payload: sem permissão de
    // leitura, mandar `cor_raca`/`saude` sobrescreveria valores que o usuário
    // nem consegue ver.
    const patch = page.waitForRequest(
      (r) => DETALHE_MEMBRO.test(new URL(r.url()).pathname) && r.method() === "PATCH",
    );
    await painel.getByLabel("CAF", { exact: true }).fill("CAF-002");
    await painel.getByRole("button", { name: "Salvar" }).click();

    const corpo = (await patch).postDataJSON() as Record<string, unknown>;
    expect(corpo).not.toHaveProperty("cor_raca");
    expect(corpo).not.toHaveProperty("saude");
    // O que o usuário de fato editou vai junto — o filtro é dos sensíveis, não
    // do formulário inteiro.
    expect(corpo.caf).toBe("CAF-002");
  });

  test("o cadastro de novo membro herda a permissão derivada da listagem", async ({
    page,
  }) => {
    // Em `create` não há detalhe carregado: `MembrosTab` deriva a permissão da
    // presença de `cor_raca_display` no primeiro item da listagem.
    await stubMembroUnico(
      page,
      sem(listaFake(), ...CHAVES_SENSIVEIS),
      sem(detalheFake(), ...CHAVES_SENSIVEIS),
    );
    await abrirAbaMembros(page, primeiroUpfId());
    const painel = await abrirFormularioNovoMembro(page);

    await expect(painel.getByLabel("Cor/Raça", { exact: true })).toHaveCount(0);
    await expect(
      painel.locator('[role="group"][aria-label="Saúde"]'),
    ).toHaveCount(0);
    await expect(painel.getByLabel("Nome completo", { exact: true })).toBeVisible();
  });

  test("perfil com permissão vê e edita os dois campos normalmente", async ({
    page,
  }) => {
    await stubMembroUnico(page, listaFake(), detalheFake());
    const painel = await abrirPainelDoMembro(page, "view");

    // Modo view: rótulo e valor, incluindo os chips de Saúde.
    await expect(rotuloNoDetalhe(painel, "Cor/Raça")).toBeVisible();
    await expect(painel.getByText("Parda", { exact: true })).toBeVisible();
    await expect(rotuloNoDetalhe(painel, "Saúde")).toBeVisible();
    await expect(painel.getByText("Diabetes", { exact: true })).toBeVisible();
    await expect(painel.getByText("Hipertensão", { exact: true })).toBeVisible();

    // Modo edit: os controles existem e vêm preenchidos com o que foi lido.
    await painel.getByRole("button", { name: "Editar" }).click();
    await expect(painel.getByLabel("Cor/Raça", { exact: true })).toContainText(
      "Parda",
    );
    await expect(chipSelecionado(painel, "Diabetes")).toBeVisible();

    // E a edição chega ao backend: troca Cor/Raça e desmarca uma condição.
    const patch = page.waitForRequest(
      (r) => DETALHE_MEMBRO.test(new URL(r.url()).pathname) && r.method() === "PATCH",
    );
    await escolherNoSelect(painel, "Cor/Raça", "Branca");
    await chipSelecionado(painel, "Hipertensão").click();
    await painel.getByRole("button", { name: "Salvar" }).click();

    const corpo = (await patch).postDataJSON() as Record<string, unknown>;
    expect(corpo).toHaveProperty("cor_raca");
    expect(corpo.saude).toEqual(["diabetes"]);
  });
});

const EXPORTAR_MEMBROS = /\/api\/v1\/sgp\/upfs\/\d+\/membros\/exportar\/$/;

/**
 * Cabeçalho completo — espelha `BASE_EXPORT_COLUMNS` + `SENSITIVE_EXPORT_COLUMNS`
 * (backend/apps/sgp/services/membro_export.py). O perfil `ugp` lê os dois campos
 * sensíveis, então recebe o arquivo inteiro.
 */
const CABECALHO_MEMBROS = [
  "ID",
  "UPF",
  "Nome completo",
  "Parentesco",
  "Data de nascimento",
  "Idade",
  "Gênero",
  "CPF",
  "Município",
  "Território",
  "Projeto",
  "Cor/Raça",
  "Condições de saúde",
].join(",");

/**
 * `membros_upf_{id}_{carimbo}.csv`.
 *
 * O separador entre data e hora depende de QUEM nomeou o arquivo: o backend usa
 * `_` no `Content-Disposition`, o fallback do cliente monta com `-`. Hoje vale
 * sempre o fallback, porque o Django não expõe `Content-Disposition` via CORS
 * (mesma observação de exportacao.spec.ts) — o regex aceita os dois para o
 * teste não quebrar no dia em que isso for corrigido.
 */
const NOME_CSV_MEMBROS =
  /^membros_upf_\d+_\d{4}-\d{2}-\d{2}[-_]\d{2}-\d{2}-\d{2}\.csv$/;

/** O backend prefixa BOM para o Excel abrir os acentos corretamente. */
function linhasDoCsv(conteudo: string): string[] {
  return conteudo
    .replace(/^﻿/, "")
    .split(/\r?\n/)
    .filter((linha) => linha !== "");
}

async function baixarCsvDeMembros(page: Page) {
  return Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("membros-exportar-csv").click(),
  ]).then(([download]) => download);
}

test.describe("SGP — Exportação de membros (CSV)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("exportar baixa o CSV com os membros daquela UPF", async ({ page }) => {
    const upfId = primeiroUpfId();
    await abrirAbaMembros(page, upfId);

    // `count()` não re-tenta: sem esperar a listagem sair do skeleton, ele lê
    // zero linhas e o teste compararia o CSV com uma tabela ainda vazia.
    const linhasNaTela = page.locator('tr[data-testid^="membro-row-"]');
    await expect(page.getByTestId("membros-loading")).toHaveCount(0);
    await expect(linhasNaTela.first()).toBeVisible();
    const naTela = await linhasNaTela.count();

    const download = await baixarCsvDeMembros(page);
    expect(download.suggestedFilename()).toMatch(NOME_CSV_MEMBROS);

    const linhas = linhasDoCsv(await readFile(await download.path(), "utf8"));
    expect(linhas[0]).toBe(CABECALHO_MEMBROS);

    // "daquela UPF específica" (AC-1): uma linha por membro da ficha aberta, e
    // nenhuma de outra UPF. As duas primeiras colunas são numéricas e nunca
    // saem entre aspas, então split(",") basta para lê-las.
    expect(linhas.length - 1).toBe(naTela);
    const upfsNoArquivo = new Set(
      linhas.slice(1).map((linha) => linha.split(",")[1]),
    );
    expect(upfsNoArquivo).toEqual(new Set([String(upfId)]));

    const toast = page.getByTestId("toast");
    await expect(toast).toBeVisible();
    await expect(toast).toContainText(download.suggestedFilename());
  });

  test("o botão indica o progresso enquanto o arquivo é gerado", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // Atraso deliberado: contra o backend real a geração desta UPF é rápida
    // demais para observar o estado intermediário sem corrida.
    const ATRASO_EXPORT_MS = 2000;
    await page.route(EXPORTAR_MEMBROS, async (route) => {
      await new Promise((r) => setTimeout(r, ATRASO_EXPORT_MS));
      await route.continue();
    });

    await abrirAbaMembros(page, upfId);

    const botao = page.getByTestId("membros-exportar-csv");
    const download = page.waitForEvent("download");
    await botao.click();

    await expect(botao).toContainText("Exportando…");
    await expect(botao).toBeDisabled();

    await download;
    await expect(botao).toContainText("Exportar CSV");
    await expect(botao).toBeEnabled();
  });

  /**
   * AC-3 e o segundo teste da issue: com a coluna sensível ausente, o arquivo
   * desce exatamente como o backend mandou e a tela não acusa erro.
   *
   * A resposta é FIXADA, e não produzida por um usuário sem permissão, porque
   * esse usuário não pode existir hoje: `UPF_ACCESS_ROLES`
   * (apps/sgp/views/__init__.py) e `SENSITIVE_FIELD_ROLES`
   * (apps/core/sensitive_fields.py) são o MESMO conjunto de quatro perfis —
   * quem não lê Saúde recebe "Você não tem acesso ao módulo SGP" e nem chega à
   * ficha. O backend esbarrou na mesma parede e resolveu com `monkeypatch`, em
   * `test_membro_export.py::test_usuario_sem_permissao_de_saude_recebe_csv_sem_a_coluna`,
   * que é onde a omissão da coluna está provada.
   *
   * O que sobra para provar aqui é o lado do frontend, e é o que a issue pede
   * dele: não completar coluna omitida e não quebrar. Ver
   * `frontend/docs/pendencias-backend-sprint-9.md`.
   */
  test("arquivo sem a coluna de Saúde desce como veio, sem erro na tela", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    const CSV_SEM_SAUDE =
      "﻿ID,UPF,Nome completo,Parentesco,Data de nascimento,Idade,Gênero,CPF,Município,Território,Projeto,Cor/Raça\r\n" +
      `1,${upfId},Maria da Silva,Titular,1980-05-02,45,Feminino,,Serra Talhada,Território PE,Projeto Dom Hélder Câmara III,Parda\r\n`;

    await page.route(EXPORTAR_MEMBROS, (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "text/csv; charset=utf-8" },
        body: CSV_SEM_SAUDE,
      }),
    );

    await abrirAbaMembros(page, upfId);
    const download = await baixarCsvDeMembros(page);

    // Byte a byte: nenhuma coluna acrescentada, nenhuma célula preenchida.
    const conteudo = await readFile(await download.path(), "utf8");
    expect(conteudo).toBe(CSV_SEM_SAUDE);

    const linhas = linhasDoCsv(conteudo);
    expect(linhas[0]).not.toContain("Condições de saúde");
    expect(linhas[0]).toContain("Cor/Raça");

    // "sem erro na tela": toast de sucesso e a aba intacta.
    const toast = page.getByTestId("toast");
    await expect(toast).toBeVisible();
    await expect(toast).toHaveAttribute("data-variant", "success");
    await expect(page.getByTestId("membros-tab")).toBeVisible();
  });
});
