import { expect, test, type Page } from "@playwright/test";
import {
  criarAtividadeFixture,
  removerAtividadeFixture,
  type AtividadeFixture,
} from "./helpers/atividadeFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Ficha de leitura da Atividade (Issue #233).
 *
 * A ficha existe desde a Issue #159 — o que esta issue acrescenta é evidência,
 * participantes navegáveis, aviso de agenda e o 404 próprio. Os testes cobrem
 * o conjunto, não só o incremento: a regressão que importa é a ficha parar de
 * abrir, não um badge sumir.
 */

let fixture: AtividadeFixture;

test.beforeAll(() => {
  fixture = criarAtividadeFixture();
});

test.afterAll(() => {
  removerAtividadeFixture();
});

/** Abre a ficha e espera o conteúdo substituir o estado de carregamento. */
async function abrirFicha(page: Page, id: number): Promise<void> {
  await page.goto(`/sgp/atividades/${id}/`);
  await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();
}

test.describe("Ficha da Atividade", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("exibe ficha completa", async ({ page }) => {
    await abrirFicha(page, fixture.comEvidencias);

    // Título em h1 — a ficha é a página, não um painel dentro de outra.
    const titulo = page.getByRole("heading", { level: 1 });
    await expect(titulo).toBeVisible();
    await expect(titulo).not.toBeEmpty();

    // Status, datas e técnico: o mínimo para reconhecer a atividade sem abrir
    // o formulário, que é a razão de a ficha existir.
    const ficha = page.getByTestId("atividade-ficha-page");
    await expect(ficha).toContainText("Técnico responsável");
    // As datas vêm na linha de resumo sob o título (dd/MM/yyyy), sem rótulo.
    await expect(ficha).toContainText(/\d{2}\/\d{2}\/\d{4}/);
    await expect(page.getByTestId("atividade-editar-btn")).toBeVisible();
  });

  test("galeria em modo leitura, sem controles de upload ou remoção", async ({
    page,
  }) => {
    await abrirFicha(page, fixture.comEvidencias);

    const evidencias = page.getByTestId("atividade-evidencias");
    await expect(evidencias).toBeVisible();

    // As fotos aparecem...
    await expect(evidencias.getByRole("img").first()).toBeVisible();

    // ...mas nada que altere o acervo.
    await expect(
      evidencias.getByRole("button", { name: /Adicionar fotos/i }),
    ).toHaveCount(0);
    await expect(
      evidencias.getByRole("button", { name: /Adicionar primeira foto/i }),
    ).toHaveCount(0);
    await expect(
      evidencias.getByRole("button", { name: /Remover foto/i }),
    ).toHaveCount(0);
    await expect(
      evidencias.getByRole("button", { name: /Adicionar documentos/i }),
    ).toHaveCount(0);
  });

  test("documentos trazem ação de download", async ({ page }) => {
    await abrirFicha(page, fixture.comEvidencias);

    const evidencias = page.getByTestId("atividade-evidencias");
    // O download é gerado por URL assinada no clique, então o que se afere é a
    // existência do controle — baixar de verdade dependeria do R2.
    await expect(
      evidencias.getByRole("button", { name: /Baixar/i }).first(),
    ).toBeVisible();
  });

  test("participantes trazem link para a ficha da UPF", async ({ page }) => {
    await abrirFicha(page, fixture.comEvidencias);

    const participantes = page.getByTestId("atividade-participantes");
    // Nem toda atividade do seed tem participante; quando tem, o link precisa
    // apontar para a ficha da UPF — que é o critério desta issue.
    if ((await participantes.count()) === 0) {
      test.skip(true, "Atividade da fixture não tem participantes");
    }

    const primeiraUpf = participantes
      .locator('[data-testid^="participante-upf-"]')
      .first();
    await expect(primeiraUpf).toBeVisible();
    // O <Link> do Next normaliza a barra final, então ela é opcional aqui.
    await expect(primeiraUpf).toHaveAttribute("href", /^\/sgp\/upfs\/\d+\/?$/);
  });

  /**
   * A ficha é COMPLETA — o critério não é "abre sem erro".
   *
   * Faltavam equipe adicional, coordenadas e auditoria, e os parceiros eram
   * lidos de `atividade.parceiros`, chave que o serializer não devolve: a
   * linha ficava permanentemente vazia enquanto a API entregava
   * `parceiros_organizacoes` e `parceiros_livres`.
   */
  test("ficha traz equipe adicional, coordenadas, parceiros e auditoria", async ({
    page,
  }) => {
    await abrirFicha(page, fixture.comFichaCompleta);

    // Equipe adicional: o M2M vem como objetos no detalhe, não como ids.
    const equipe = page.getByTestId("atividade-equipe-adicional");
    await expect(equipe).toBeVisible();
    await expect(equipe.getByRole("listitem").first()).not.toBeEmpty();

    await expect(page.getByTestId("atividade-coordenadas")).toContainText(
      `${fixture.latitude}, ${fixture.longitude}`,
    );

    await expect(page.getByTestId("atividade-parceiros")).toContainText(
      fixture.parceirosLivres,
    );

    const auditoria = page.getByTestId("atividade-auditoria");
    await expect(auditoria).toContainText("Criado por");
    await expect(auditoria).toContainText("Criado em");
    await expect(auditoria).toContainText("Última atualização");
    // Datas resolvidas, e não o em-dash de "campo ausente".
    await expect(auditoria).toContainText(/\d{2}\/\d{2}\/\d{4}/);
  });

  /**
   * O membro também navega.
   *
   * As UPFs tinham link e os membros eram texto morto. O membro não tem rota
   * própria — a dele é a aba de membros da UPF —, e o payload da atividade não
   * diz qual UPF é; a ficha resolve o vínculo cruzando com os membros das UPFs
   * participantes.
   */
  test("membro participante leva à aba de membros da UPF", async ({ page }) => {
    await abrirFicha(page, fixture.comFichaCompleta);

    const membro = page.getByTestId(
      `participante-membro-${fixture.membroParticipante}`,
    );
    await expect(membro).toBeVisible();
    await expect(membro).toHaveAttribute(
      "href",
      new RegExp(`^/sgp/upfs/${fixture.upfDoMembro}/?#membros$`),
    );

    await membro.click();
    await expect(page).toHaveURL(
      new RegExp(`/sgp/upfs/${fixture.upfDoMembro}/?#membros$`),
    );
    // Chegou na aba certa, e não só na ficha da UPF — e o membro clicado está
    // naquela lista. Afirmar a LINHA dele é mais forte que procurar um título:
    // prova que o cruzamento membro → UPF acertou a ficha, não só a rota.
    await expect(page.getByTestId("membros-tab")).toBeVisible();
    await expect(
      page.getByTestId(`membro-row-${fixture.membroParticipante}`),
    ).toBeVisible();
  });

  /**
   * Ícone por TIPO de documento, não a mesma folha de PDF em toda linha.
   *
   * O upload aceita só PDF, então um ícone por formato não informaria nada — o
   * que distingue uma ata de uma lista de presença é a função do documento.
   */
  test("documentos trazem ícone por tipo", async ({ page }) => {
    await abrirFicha(page, fixture.comEvidencias);

    const icone = page
      .getByTestId("atividade-evidencias")
      .locator('[data-testid^="documento-icone-"]')
      .first();
    await expect(icone).toBeVisible();

    // O tipo do documento vai no testid e no rótulo acessível: o ícone é a
    // única marca do tipo antes da etiqueta na leitura por voz.
    const testid = await icone.getAttribute("data-testid");
    expect(testid).toMatch(
      /^documento-icone-(lista_presenca|ata|relatorio_parcial|declaracao|contrato|outro)$/,
    );
    await expect(icone).toHaveAttribute("aria-label", /.+/);
  });

  test("badge de erro do Google Calendar aparece sem quebrar a página", async ({
    page,
  }) => {
    await abrirFicha(page, fixture.comErroDeAgenda);

    await expect(page.getByTestId("badge-calendar-erro")).toBeVisible();
    // "Sem bloquear a página" é parte do critério: o resto da ficha continua lá.
    await expect(page.getByTestId("atividade-editar-btn")).toBeVisible();
  });

  test("atividade sem erro de agenda não exibe o badge", async ({ page }) => {
    await abrirFicha(page, fixture.comEvidencias);
    await expect(page.getByTestId("badge-calendar-erro")).toHaveCount(0);
  });

  test("clique na linha da listagem abre o detalhe, não a edição", async ({
    page,
  }) => {
    await page.goto("/sgp/atividades/");

    // nth(1) pega o skeleton enquanto a lista carrega; esperar por uma linha
    // com conteúdo garante que o onClick já está montado.
    const linha = page
      .getByRole("row")
      .filter({ hasText: /\d{2}\/\d{2}\/\d{4}/ })
      .first();
    await expect(linha).toBeVisible();
    await linha.click();

    await expect(page).toHaveURL(/\/sgp\/atividades\/\d+\/?$/);
    await expect(page).not.toHaveURL(/\/editar\/?$/);
    await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();
  });

  test("id inexistente renderiza o not-found da rota", async ({ page }) => {
    await page.goto("/sgp/atividades/99999999/");

    // O not-found.tsx da rota, e não o 404 genérico do Next: o texto é o que
    // distingue os dois.
    await expect(
      page.getByText(/Atividade não encontrada ou fora do seu escopo/i),
    ).toBeVisible();
  });
});
