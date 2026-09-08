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
