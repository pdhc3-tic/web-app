import { expect, test, type Page } from "@playwright/test";
import {
  APROVADO_NACIONAL,
  comprometerNacional,
  criarDistribuicaoFixture,
  ESTADO_COM_COMPROMETIDO,
  ESTADO_LIVRE,
  removerDistribuicaoFixture,
  RUBRICA,
  valorAlocadoNoBanco,
} from "./helpers/distribuicaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Distribuição orçamentária (§5.3.2) — a tela de escrita do orçamento.
 *
 * A UGP distribui o nacional entre os estados; o Articulador redistribui o seu
 * estado entre os territórios. Quem pode o quê é `_autorizar` no backend; estes
 * testes cobrem a afordância, o feedback de teto e o caminho do erro.
 *
 * ─── Por que cada teste remonta a fixture ───────────────────────────────────
 *
 * Esta suíte GRAVA. Um teste que distribui muda o "já distribuído" que o
 * seguinte usaria como ponto de partida, e a ordem de execução passaria a ser
 * parte do contrato de cada asserção. O beforeEach devolve o banco ao mesmo
 * estado, ao custo de um shell por teste.
 */

test.beforeEach(() => {
  criarDistribuicaoFixture();
});

test.afterAll(() => {
  removerDistribuicaoFixture();
});

/** Abre a tela e escolhe Meta + rubrica, que é o recorte mínimo para operar. */
async function abrirRecorte(page: Page): Promise<void> {
  await page.goto("/sgp/orcamento/distribuicao");
  await expect(page.getByTestId("distribuicao-page")).toBeVisible();

  await page.locator("#distribuicao-meta").click();
  await page
    .locator('li[role="option"]')
    .filter({ hasText: /^Meta 7\b/ })
    .click();

  await page.locator("#distribuicao-rubrica").click();
  await page
    .locator('li[role="option"]')
    .filter({ hasText: new RegExp(`^${RUBRICA.nome}$`) })
    .click();

  await expect(page.getByTestId("distribuicao-barra-saldo")).toBeVisible();
}

/** Id do State a partir da linha renderizada — o testid carrega a PK. */
async function idDoDestino(page: Page, nomeParcial: string): Promise<string> {
  const linha = page
    .locator('[data-testid^="distribuicao-destino-"]')
    .filter({ hasText: nomeParcial })
    .first();
  await expect(linha).toBeVisible();
  const testid = await linha.getAttribute("data-testid");
  return testid!.replace("distribuicao-destino-", "");
}

test.describe("Distribuição orçamentária — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("painel leva a distribuicao", async ({ page }) => {
    await page.goto("/sgp/orcamento/");
    await expect(page.getByTestId("orcamento-page")).toBeVisible();

    // O <Button> do design system só vira <a> com `as="a"`; sem isso o `href`
    // fica pendurado num <button> e o clique não navega. Nada na tela denuncia
    // isso, então o caminho precisa de teste.
    const ir = page.getByTestId("orcamento-ir-distribuicao");
    await expect(ir).toBeVisible();
    await ir.click();

    await expect(page).toHaveURL(/\/sgp\/orcamento\/distribuicao/);
    await expect(page.getByTestId("distribuicao-page")).toBeVisible();
  });

  test("ugp distribui por estado", async ({ page }) => {
    await abrirRecorte(page);

    // Ponto de partida: só o estado com comprometido está distribuído.
    const barra = page.getByTestId("distribuicao-barra-saldo");
    await expect(barra).toContainText(
      new RegExp(`R\\$\\s*${ESTADO_COM_COMPROMETIDO.alocado.toLocaleString("pt-BR")},00`),
    );

    const id = await idDoDestino(page, ESTADO_LIVRE.sigla);
    await page.getByTestId(`distribuicao-valor-${id}`).fill("2000000");

    await page.getByTestId(`distribuicao-submit-${id}`).click();
    await page.getByTestId("distribuicao-confirmar").click();

    // Toast de sucesso e barra refeita, sem recarregar a página.
    await expect(page.getByRole("status").first()).toContainText(
      /distribuído/i,
    );
    await expect(barra).toContainText(/R\$\s*30\.000,00/);

    expect(valorAlocadoNoBanco(ESTADO_LIVRE.sigla)).toBe("20000.00");
  });

  test("bloqueia acima do teto", async ({ page }) => {
    await abrirRecorte(page);

    const id = await idDoDestino(page, ESTADO_LIVRE.sigla);
    // 10.000 já distribuídos + 95.000 = 105.000 contra um teto de 100.000.
    await page.getByTestId(`distribuicao-valor-${id}`).fill("9500000");

    await expect(page.getByTestId(`distribuicao-submit-${id}`)).toBeDisabled();

    // O excedente vem escrito, não só pela cor da barra.
    const excedente = page.getByTestId("distribuicao-excedente");
    await expect(excedente).toBeVisible();
    await expect(excedente).toContainText(/R\$\s*5\.000,00/);
    await expect(page.getByTestId("distribuicao-barra-saldo")).toHaveAttribute(
      "data-estourou",
      "sim",
    );

    // Reduzindo para caber, o botão volta — a trava é do valor, não do estado
    // da tela.
    await page.getByTestId(`distribuicao-valor-${id}`).fill("5000000");
    await expect(page.getByTestId(`distribuicao-submit-${id}`)).toBeEnabled();
    await expect(page.getByTestId("distribuicao-excedente")).toHaveCount(0);
  });

  /**
   * A barra mostra a conta INTEIRA, e não só o saldo já líquido.
   *
   * Com comprometido no pai, `saldoDoPai` fica menor que o alocado. A barra
   * começava justamente no saldo, então o total de origem sumia da tela e a
   * diferença não tinha explicação nenhuma — parecia que o sistema havia
   * perdido dinheiro. As quatro parcelas precisam fechar:
   *
   *     100.000 alocado − 25.000 comprometido − 10.000 distribuído = 65.000
   */
  test("barra mostra alocado, comprometido, distribuido e disponivel", async ({
    page,
  }) => {
    const comprometido = 25000;
    comprometerNacional(comprometido);

    await abrirRecorte(page);

    const brl = (n: number) =>
      new RegExp(`R\\$\\s*${n.toLocaleString("pt-BR")},00`);

    await expect(page.getByTestId("distribuicao-alocado")).toHaveText(
      brl(APROVADO_NACIONAL),
    );
    await expect(page.getByTestId("distribuicao-consumido")).toContainText(
      brl(comprometido),
    );
    await expect(page.getByTestId("distribuicao-distribuido")).toHaveText(
      brl(ESTADO_COM_COMPROMETIDO.alocado),
    );
    await expect(page.getByTestId("distribuicao-disponivel")).toHaveText(
      brl(APROVADO_NACIONAL - comprometido - ESTADO_COM_COMPROMETIDO.alocado),
    );
  });

  /**
   * Dois destinos editados ao mesmo tempo.
   *
   * Cada valor cabe sozinho contra o teto, mas os dois somados o estouram. Era
   * o buraco do bloqueio antigo: o excedente era medido destino a destino, a
   * barra somava os dois rascunhos e desenhava o total acima do teto, e mesmo
   * assim os DOIS botões continuavam habilitados, sem mensagem nenhuma. Na
   * prática a primeira gravação passaria e a segunda levaria 400 — cada POST é
   * validado sozinho contra o que já está no banco.
   */
  test("bloqueia dois destinos que so estouram somados", async ({ page }) => {
    await abrirRecorte(page);

    const idPe = await idDoDestino(page, ESTADO_LIVRE.sigla);
    const idPb = await idDoDestino(page, ESTADO_COM_COMPROMETIDO.sigla);

    // 10.000 já distribuídos em PB. Cada um sozinho cabe no teto de 100.000:
    // PE → 10.000 + 80.000 = 90.000; PB → 0 + 90.000 = 90.000.
    await page.getByTestId(`distribuicao-valor-${idPe}`).fill("8000000");
    await expect(page.getByTestId(`distribuicao-submit-${idPe}`)).toBeEnabled();

    await page.getByTestId(`distribuicao-valor-${idPb}`).fill("9000000");

    // Juntos: 170.000 contra 100.000.
    const excedente = page.getByTestId("distribuicao-excedente");
    await expect(excedente).toBeVisible();
    await expect(excedente).toContainText(/R\$\s*70\.000,00/);
    await expect(excedente).toContainText(/2 valores em edição/i);

    await expect(page.getByTestId("distribuicao-barra-saldo")).toHaveAttribute(
      "data-estourou",
      "sim",
    );

    // Os dois botões travam: nenhum dos dois valores é "o culpado" sozinho.
    await expect(page.getByTestId(`distribuicao-submit-${idPe}`)).toBeDisabled();
    await expect(page.getByTestId(`distribuicao-submit-${idPb}`)).toBeDisabled();

    // E cada linha diz por que travou, sem obrigar a ler a barra.
    await expect(page.getByTestId(`distribuicao-motivo-${idPe}`)).toContainText(
      /somado aos outros/i,
    );

    // Reduzindo um deles, os dois voltam: a trava é da soma.
    await page.getByTestId(`distribuicao-valor-${idPb}`).fill("1000000");
    await expect(page.getByTestId("distribuicao-excedente")).toHaveCount(0);
    await expect(page.getByTestId(`distribuicao-submit-${idPe}`)).toBeEnabled();
  });

  test("erro do servidor no campo certo", async ({ page }) => {
    await abrirRecorte(page);

    // Reduzir abaixo do comprometido é recusado pelo servidor, e a tela não tem
    // como antecipar: ela valida teto, não piso. É o caso que prova que o 400
    // chega ancorado no input, e não num alerta solto.
    const id = await idDoDestino(page, ESTADO_COM_COMPROMETIDO.sigla);
    await page.getByTestId(`distribuicao-valor-${id}`).fill("500000");

    await expect(page.getByTestId(`distribuicao-submit-${id}`)).toBeEnabled();
    await page.getByTestId(`distribuicao-submit-${id}`).click();
    await page.getByTestId("distribuicao-confirmar").click();

    // A mensagem do servidor, dentro da linha do destino recusado.
    const linha = page.getByTestId(`distribuicao-destino-${id}`);
    await expect(linha).toContainText(/reduzir abaixo do já comprometido/i);
    await expect(linha).toContainText(
      new RegExp(`${ESTADO_COM_COMPROMETIDO.comprometido}`),
    );

    // E nada foi gravado.
    expect(valorAlocadoNoBanco(ESTADO_COM_COMPROMETIDO.sigla)).toBe(
      `${ESTADO_COM_COMPROMETIDO.alocado}.00`,
    );
  });

  test("confirmacao antes de gravar", async ({ page }) => {
    await abrirRecorte(page);

    const id = await idDoDestino(page, ESTADO_LIVRE.sigla);
    await page.getByTestId(`distribuicao-valor-${id}`).fill("150000");
    await page.getByTestId(`distribuicao-submit-${id}`).click();

    // O resumo repete o recorte inteiro: quem chega aqui depois de mexer nos
    // selects precisa ver contra o que está gravando.
    const dialogo = page.getByTestId("distribuicao-confirmacao");
    await expect(dialogo).toBeVisible();
    await expect(dialogo).toContainText("Meta 7");
    await expect(dialogo).toContainText(RUBRICA.nome);
    await expect(dialogo).toContainText(ESTADO_LIVRE.sigla);
    await expect(dialogo).toContainText("Estadual");
    await expect(dialogo).toContainText(/R\$\s*1\.500,00/);

    // Cancelar não grava: a confirmação é a decisão, não uma formalidade.
    await page.getByTestId("distribuicao-cancelar").click();
    await expect(page.getByTestId("distribuicao-confirmacao")).toHaveCount(0);
    expect(valorAlocadoNoBanco(ESTADO_LIVRE.sigla)).toBeNull();
  });

  test("mascara aceita formato brasileiro", async ({ page }) => {
    await abrirRecorte(page);

    const id = await idDoDestino(page, ESTADO_LIVRE.sigla);
    const campo = page.getByTestId(`distribuicao-valor-${id}`);

    // Colar o formato brasileiro inteiro, com separador de milhar e vírgula.
    await campo.fill("1.234,56");
    await expect(campo).toHaveValue(/R\$\s*1\.234,56/);

    await page.getByTestId(`distribuicao-submit-${id}`).click();
    await page.getByTestId("distribuicao-confirmar").click();
    await expect(page.getByRole("status").first()).toContainText(/distribuído/i);

    // O que importa é o decimal que chegou ao banco: a tela reexibiria
    // "R$ 1.234,56" tanto para 1234.56 quanto para um valor errado reformatado.
    expect(valorAlocadoNoBanco(ESTADO_LIVRE.sigla)).toBe("1234.56");
  });
});

test.describe("Distribuição orçamentária — Articulador Estadual", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("articulador limitado ao seu estado", async ({ page }) => {
    await page.goto("/sgp/orcamento/distribuicao");
    await expect(page.getByTestId("distribuicao-page")).toBeVisible();

    // Ele redistribui aos territórios, então escolhe de qual estado — e a lista
    // tem só os dele. `_autorizar` recusaria qualquer outro.
    await page.locator("#distribuicao-estado").click();
    const opcoes = page.locator('li[role="option"]');

    for (const sigla of ["PE", "AL", "MA"]) {
      await expect(opcoes.filter({ hasText: new RegExp(`^${sigla}$`) })).toHaveCount(1);
    }
    for (const sigla of ["PB", "RN", "BA", "MG"]) {
      await expect(opcoes.filter({ hasText: new RegExp(`^${sigla}$`) })).toHaveCount(0);
    }
  });
});

test.describe("Distribuição orçamentária — ADT/ACR", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("adt recebe restricted access", async ({ page }) => {
    await page.goto("/sgp/orcamento/distribuicao");

    // `getByRole("alert")` pegaria junto o route-announcer do Next, que também
    // é role=alert e vive vazio no fim do body.
    await expect(
      page.getByRole("alert").filter({ hasText: "Distribuição restrita" }),
    ).toBeVisible();
    // Nenhuma afordância de escrita sobra na tela.
    await expect(page.getByTestId("distribuicao-destinos")).toHaveCount(0);
    await expect(page.locator("#distribuicao-meta")).toHaveCount(0);
  });
});
