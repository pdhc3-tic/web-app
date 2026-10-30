import { expect, test, type Page } from "@playwright/test";
import {
  contarAnexos,
  criarAtividadesFixture,
  desativarFotos,
  PREFIXO_B6,
  removerAtividadesFixture,
  type AtividadesFixture,
} from "./helpers/atividadesFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Atividades de campo do SGP contra o backend real (B6 da #302): criação,
 * listagem, evidências (upload de foto e de documento pelo storage local) e a
 * transição para Concluído com e sem evidência. As atividades vêm da fixture
 * (`atividadesFixture.ts`); nenhuma resposta é simulada.
 */

let fx: AtividadesFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarAtividadesFixture();
});

test.afterAll(() => {
  removerAtividadesFixture();
});

/**
 * Abre o formulário de nova atividade já hidratado: o técnico responsável vem
 * preenchido com o usuário depois que a tela carrega os dados. Antes disso, o
 * React descarta o que for digitado.
 */
async function abrirNovaAtividade(page: Page) {
  await page.goto("/sgp/atividades/nova");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("#atividade-tecnico-responsavel")).not.toHaveText(/Selecione/);
}

/** Abre um `Select` do design system pelo id e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

test.describe("SGP — Criação de atividade", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("submit sem campos obrigatórios exibe erros inline", async ({ page }) => {
    await abrirNovaAtividade(page);

    await page.getByRole("button", { name: "Salvar", exact: true }).click();

    await expect(page.getByText("Informe o título da atividade.")).toBeVisible();
    await expect(page.getByText("Selecione o tipo de atividade.")).toBeVisible();
    await expect(page.getByText("Selecione a Ação do PT.")).toBeVisible();
    await expect(page.getByText("Selecione a forma de atuação.")).toBeVisible();
    await expect(page.getByText("Descreva a atividade.")).toBeVisible();
  });

  test("data de fim anterior à de início exibe mensagem de erro", async ({
    page,
  }) => {
    await abrirNovaAtividade(page);

    await page.locator("#atividade-data-inicio").fill("2026-06-10");
    await page.locator("#atividade-data-fim").fill("2026-06-05");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();

    await expect(
      page.getByText("A data de fim não pode ser anterior à data de início."),
    ).toBeVisible();
  });

  test("preencher só o título ainda cobra os demais obrigatórios", async ({
    page,
  }) => {
    await abrirNovaAtividade(page);

    await page.locator("#atividade-titulo").fill("Teste de obrigatórios");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();

    await expect(page.getByText("Selecione o tipo de atividade.")).toBeVisible();
  });

  test("criação bem-sucedida grava no backend e leva à atividade", async ({ page }) => {
    await abrirNovaAtividade(page);

    await page.locator("#atividade-titulo").fill(`${PREFIXO_B6} Visita criada pela tela`);
    await escolher(page, "atividade-tipo-atividade", "Visita técnica");
    await escolher(page, "atividade-forma-atuacao", "Realização");

    // AcaoCombobox: digitar abre a lista das Ações do Plano de Trabalho.
    await page.locator("#atividade-acao").fill("1.");
    await page.getByRole("option").first().click();

    await escolher(page, "atividade-tecnico-responsavel", /.+/);
    await escolher(page, "atividade-estado", /\(RN\)/);
    await expect(page.locator("#atividade-municipio")).toBeEnabled();
    await escolher(page, "atividade-municipio", /.+/);
    await escolher(page, "atividade-ambito", "Municipal");

    await page.locator("#atividade-data-inicio").fill("2026-11-10");
    await page.locator("#atividade-data-fim").fill("2026-11-10");
    await page.locator("#atividade-descricao-narrativa").fill("Visita de acompanhamento criada pelo E2E.");

    const criacao = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/v1/sgp/atividades/" && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    const resposta = await criacao;
    expect(resposta.status()).toBe(201);
    const { id } = (await resposta.json()) as { id: number };
    await page.waitForURL(new RegExp(`/sgp/atividades/${id}/`));
  });
});

test.describe("SGP — Listagem de atividades", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("listagem renderiza atividades do seed com colunas corretas", async ({ page }) => {
    await page.goto("/sgp/atividades");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Atividade" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Status" })).toBeVisible();
  });

  test("filtro por Concluído sem evidência traz só as pendentes, com o selo certo", async ({ page }) => {
    await page.goto("/sgp/atividades?status=concluido_sem_evidencia");
    const pendente = page.getByRole("row").filter({ hasText: fx.pendente.titulo });
    await expect(pendente).toBeVisible();
    await expect(pendente).toContainText("Concluído sem evidência");
    // As da fixture em andamento ficam de fora do filtro.
    await expect(page.getByRole("row").filter({ hasText: fx.semEvidencia.titulo })).toHaveCount(0);
  });

  test("estado vazio com filtros ativos exibe botão Limpar filtros", async ({ page }) => {
    await page.goto("/sgp/atividades?status=concluido&de=2000-01-01&ate=2000-01-02");
    await expect(page.getByRole("heading", { name: "Nenhuma atividade neste período." })).toBeVisible();
    // O botão do estado vazio (o outro fica na barra de filtros) limpa tudo.
    await page.getByRole("button", { name: "Limpar filtros" }).last().click();
    await expect(page).not.toHaveURL(/status=/);
    await expect(page.getByRole("columnheader", { name: "Atividade" })).toBeVisible();
  });
});

test.describe("SGP — Evidências (fotos e documentos)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a edição mostra a galeria de fotos e a seção de documentos", async ({ page }) => {
    await page.goto(`/sgp/atividades/${fx.comFoto.id}/editar`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Fotos/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Documentos/i })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Adicionar foto/i }).or(page.getByLabel(/Adicionar foto/i)).first(),
    ).toBeVisible();
  });

  test("upload de foto passa pelo storage e fica gravado na atividade", async ({ page }) => {
    await page.goto(`/sgp/atividades/${fx.anexos.id}/editar`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached();
    await fileInput.setInputFiles({ name: "foto-teste.jpg", mimeType: "image/jpeg", buffer: Buffer.alloc(1024) });

    const confirmacao = page.waitForResponse(
      (r) => r.url().includes(`/atividades/${fx.anexos.id}/fotos/confirm/`) && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /Enviar .* foto/i }).click();
    expect((await confirmacao).status()).toBe(201);
    await expect.poll(() => contarAnexos(fx.anexos.id).fotos).toBe(1);
  });

  test("upload de documento PDF passa pelo storage e aparece na lista", async ({ page }) => {
    await page.goto(`/sgp/atividades/${fx.anexos.id}/editar`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const docInput = page.locator('input[type="file"][accept*="pdf"]');
    await expect(docInput).toBeAttached();
    await docInput.setInputFiles({ name: "ata-reuniao.pdf", mimeType: "application/pdf", buffer: Buffer.alloc(1024) });

    // "Tipo" é um combobox do design system, escopado pela seção de Documentos
    // para não colidir com o "Tipo de atividade" do formulário principal.
    const docSection = page.getByRole("region", { name: "Documentos da atividade" });
    await docSection.getByRole("combobox", { name: "Tipo" }).click();
    await page.getByRole("option", { name: "Ata" }).click();
    await docSection.locator('input[type="date"]').last().fill("2026-06-01");

    const confirmacao = page.waitForResponse(
      (r) => r.url().includes(`/atividades/${fx.anexos.id}/documentos/confirm/`) && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Enviar pendentes" }).click();
    expect((await confirmacao).status()).toBe(201);
    await expect(docSection.getByText("ata-reuniao.pdf", { exact: false })).toBeVisible();
    expect(contarAnexos(fx.anexos.id).documentos).toBe(1);

    // Recarregar mostra o documento vindo do backend, não do estado da tela.
    await page.reload();
    await expect(
      page.getByRole("region", { name: "Documentos da atividade" }).getByText("ata-reuniao.pdf", { exact: false }),
    ).toBeVisible();
  });
});

test.describe("SGP — Transição de status", () => {
  test.use({ storageState: storageStatePath("ugp") });

  async function abrirTransicaoParaConcluido(page: Page, atividadeId: number) {
    await page.goto(`/sgp/atividades/${atividadeId}/`);
    await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();
    await page.getByTestId("atividade-status-btn").click();
    await expect(page.getByTestId("transicao-dialog")).toBeVisible();
    await page.getByLabel("Novo status").click();
    await page.getByRole("option", { name: "Concluído", exact: true }).click();
  }

  test("sem evidência: aviso aparece e Confirmar fica desabilitado", async ({ page }) => {
    await abrirTransicaoParaConcluido(page, fx.semEvidencia.id);
    await expect(page.getByTestId("transicao-aviso-evidencia")).toBeVisible();
    await expect(page.getByTestId("transicao-confirmar")).toBeDisabled();
  });

  test("foto removida depois de abrir a ficha: o backend recusa e a mensagem aparece", async ({ page }) => {
    await abrirTransicaoParaConcluido(page, fx.fotoRemovida.id);
    await expect(page.getByTestId("transicao-confirmar")).toBeEnabled();

    // Outra aba remove a única foto: a tela ainda acha que há evidência.
    desativarFotos(fx.fotoRemovida.id);
    const patch = page.waitForResponse(
      (r) => r.url().includes(`/sgp/atividades/${fx.fotoRemovida.id}/`) && r.request().method() === "PATCH",
    );
    await page.getByTestId("transicao-confirmar").click();
    expect((await patch).status()).toBe(400);

    await expect(page.getByTestId("transicao-erro")).toContainText("sem ao menos uma foto ou documento");
    await expect(page.getByTestId("transicao-dialog")).toBeVisible();
  });

  test("com evidência: conclui no backend e o diálogo fecha", async ({ page }) => {
    await abrirTransicaoParaConcluido(page, fx.comFoto.id);
    await expect(page.getByTestId("transicao-aviso-evidencia")).toHaveCount(0);

    const patch = page.waitForResponse(
      (r) => r.url().includes(`/sgp/atividades/${fx.comFoto.id}/`) && r.request().method() === "PATCH",
    );
    await page.getByTestId("transicao-confirmar").click();
    const resposta = await patch;
    expect(resposta.status()).toBe(200);
    expect(((await resposta.json()) as { status: string }).status).toBe("concluido");
    await expect(page.getByTestId("transicao-dialog")).toHaveCount(0);
  });
});
