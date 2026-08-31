import { execFileSync } from "node:child_process";
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
 * A asserção do badge do Titular mora aqui, e não num teste de componente,
 * porque o projeto ainda não tem runner de componente (mesma pendência da
 * issue 133). Ao montar o runner, ela pode migrar para `MembrosTab.test.tsx`.
 */

/** Regex do GET da listagem — não pega o detalhe (`/membros/{id}/`). */
const LISTA_MEMBROS = /\/api\/v1\/sgp\/upfs\/\d+\/membros\/(\?|$)/;

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

  test("UPF sem membros exibe o estado vazio com CTA para cadastrar o Titular", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    await page.route(LISTA_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });

    await abrirAbaMembros(page, upfId);

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
