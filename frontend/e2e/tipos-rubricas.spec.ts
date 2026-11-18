import { expect, test, type Page } from "@playwright/test";
import {
  criarTipoRubricaFixture,
  removerTipoRubricaFixture,
  type TipoRubricaFixture,
} from "./helpers/tipoRubricaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #365 (SGD-REF-FE-07) — Configurações → SGD → Tipos de solicitação: o
 * catálogo de tipos (`/sgd/config/tipos-solicitacao/`, #357) e o formulário de
 * solicitação guiado por ele, contra o backend real, sem resposta simulada.
 *
 * O Super Admin cria o tipo "Hospedagem" com o schema dos campos, e o ADT o
 * solicita na montagem da demanda: o formulário é desenhado pelo schema, e a
 * solicitação sai na rubrica do tipo. Desativado, o tipo some do formulário.
 *
 * O schema tem um campo de anexo (`format: anexo`, PR #422): o PDF sobe pelo
 * fluxo de documentos da demanda, o campo guarda o id do documento, e o cartão
 * mostra o arquivo. A aba Documentos não o lista.
 */

let fx: TipoRubricaFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarTipoRubricaFixture();
});

test.afterAll(() => {
  if (fx) removerTipoRubricaFixture(fx);
});

const TELA = "/admin/configuracoes/sgd/tipos-rubricas";
const AVISO = "vale só para novas solicitações";

const SCHEMA_HOSPEDAGEM = {
  type: "object",
  required: ["hotel", "diarias", "check_in", "comprovante"],
  properties: {
    hotel: { type: "string", title: "Hotel", "x-ordem": 1 },
    diarias: { type: "integer", title: "Número de diárias", minimum: 1, "x-ordem": 2 },
    check_in: { type: "string", format: "date", title: "Check-in", "x-ordem": 3 },
    cafe: { type: "boolean", title: "Café incluso?", "x-ordem": 4 },
    comprovante: { type: "integer", format: "anexo", title: "Comprovante de reserva", "x-ordem": 5 },
  },
};

const pdf = (name: string) => ({
  name,
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"),
});

let solicitacaoId: number;

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao, exact: true }).click();
}

async function abrirNovaSolicitacao(page: Page) {
  await page.goto(`/sgd/demandas/${fx.demanda.id}/editar`);
  await expect(page.getByTestId("montar-demanda")).toBeVisible();
  await page.getByTestId("solicitacao-adicionar").click();
  return page.getByTestId("solicitacao-form");
}

test.describe("Super Admin — catálogo", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("chega pela área de Configurações e vê os tipos do catálogo com a rubrica", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Configurações" }).click();
    await expect(page).toHaveURL(/\/admin\/configuracoes\/?$/);
    await page.getByTestId("configuracao-card-tipos-rubricas").click();
    await expect(page).toHaveURL(new RegExp(`${TELA}/?$`));

    const tabela = page.getByTestId("tipos-tabela");
    for (const t of fx.tipos.filter((x) => x.ativo)) {
      await expect(tabela.getByTestId(`tipo-${t.slug}`)).toContainText(t.nome);
      await expect(tabela.getByTestId(`tipo-${t.slug}`)).toContainText("Ativo");
    }
    await expect(tabela.getByTestId("tipo-veiculo")).toContainText("Locação de Veículo");
  });

  test("um tipo de origem: identificador fixo e a validação própria só para leitura", async ({ page }) => {
    await page.goto(TELA);
    await page.getByTestId("tipo-editar-veiculo").click();
    const form = page.getByTestId("tipo-form");
    await expect(form.getByLabel("Identificador")).toBeDisabled();
    await expect(form.getByTestId("tipo-validador")).toContainText("veiculo");
    // A pré-visualização é o layout próprio do veículo, não o desenhado pelo schema.
    await expect(form.getByTestId("tipo-previa")).toContainText("Tipo de veículo");
  });

  test("cria o tipo Hospedagem, com a pré-visualização dos campos do schema", async ({ page }) => {
    await page.goto(TELA);
    await page.getByTestId("tipo-novo").click();
    const form = page.getByTestId("tipo-form");

    await form.getByLabel("Nome").fill("Hospedagem");
    await expect(form.getByLabel("Identificador")).toHaveValue("hospedagem");
    await escolher(page, "tipo-rubrica", "Diárias");
    await form.getByLabel("Ordem").fill("7");

    const editor = form.getByLabel(/Campos do formulário/);
    await editor.fill("{ quebrado");
    await expect(form).toContainText("JSON inválido");
    await editor.fill(JSON.stringify(SCHEMA_HOSPEDAGEM, null, 2));
    const previa = form.getByTestId("tipo-previa");
    await expect(previa).toContainText("Hotel");
    await expect(previa).toContainText("Número de diárias");
    await expect(previa).toContainText("Café incluso?");
    // Na pré-visualização não há demanda: o anexo aparece, mas não envia.
    await expect(previa.getByTestId("campo-comprovante").locator("input[type=file]")).toBeDisabled();

    await page.getByTestId("tipo-salvar").click();
    await expect(page.getByText(`Tipo criado. A alteração ${AVISO}`)).toBeVisible();
    const linha = page.getByTestId("tipo-hospedagem");
    await expect(linha).toContainText("Hospedagem");
    await expect(linha).toContainText("Diárias");
    await expect(linha).toContainText("Ativo");
  });
});

test.describe("ADT — solicita o tipo novo", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o formulário é desenhado pelo schema, e a solicitação sai na rubrica do tipo", async ({ page }) => {
    const form = await abrirNovaSolicitacao(page);
    await escolher(page, "solicitacao-tipo", "Hospedagem");

    // Obrigatórios do schema são conferidos antes de enviar.
    await page.getByTestId("solicitacao-salvar").click();
    await expect(form.getByText("Campo obrigatório.").first()).toBeVisible();

    await form.getByLabel("Hotel").fill("Pousada do Sertão");
    await form.getByLabel("Número de diárias").fill("2");
    await form.getByLabel("Check-in").fill("2026-12-10");
    await form.getByTestId("campo-cafe").getByLabel("Sim").check();
    await form.getByLabel("Valor estimado").fill("36000");

    // O anexo sobe na hora, como documento da demanda do tipo "anexo".
    const envio = page.waitForResponse((r) => r.url().includes("/documentos/confirm/"));
    await form.locator("#campo-comprovante").setInputFiles(pdf("reserva-pousada.pdf"));
    expect((await envio).status()).toBe(201);
    await expect(form.getByTestId("campo-comprovante")).toContainText("reserva-pousada.pdf");
    // O saldo consultado é o da rubrica do tipo.
    await expect(form.getByTestId("saldo-solicitacao")).toContainText("Diárias");

    const criacao = page.waitForResponse(
      (r) => r.url().includes(`/api/v1/sgd/demandas/${fx.demanda.id}/solicitacoes/`) && r.request().method() === "POST",
    );
    await page.getByTestId("solicitacao-salvar").click();
    const resposta = await criacao;
    expect(resposta.status()).toBe(201);
    const salva = (await resposta.json()) as {
      id: number;
      campos_json: Record<string, unknown>;
      rubrica_slug: string;
      anexos: Record<string, { id: number; nome_original: string } | null>;
    };
    expect(salva.rubrica_slug).toBe("diarias");
    expect(salva.campos_json).toMatchObject({ hotel: "Pousada do Sertão", diarias: 2, check_in: "2026-12-10", cafe: true });
    expect(salva.campos_json.comprovante).toBe(salva.anexos.comprovante?.id);
    expect(salva.anexos.comprovante?.nome_original).toBe("reserva-pousada.pdf");
    solicitacaoId = salva.id;

    const cartao = page.getByTestId(`solicitacao-${salva.id}`);
    await expect(cartao).toContainText("Hospedagem");
    await expect(cartao).toContainText("Pousada do Sertão · 2");
    const anexos = cartao.getByTestId(`anexos-solicitacao-${salva.id}`);
    await expect(anexos).toContainText("Comprovante de reserva:");
    await expect(anexos.getByTestId(`anexo-${salva.anexos.comprovante?.id}`)).toHaveText("reserva-pousada.pdf");
    // O anexo é da solicitação: a aba Documentos não o lista.
    await expect(page.getByTestId("documentos-demanda")).not.toContainText("reserva-pousada.pdf");
  });

  test("trocar o anexo: o arquivo novo entra no campo, e o antigo sai da demanda", async ({ page }) => {
    await page.goto(`/sgd/demandas/${fx.demanda.id}/editar`);
    await page.getByTestId(`solicitacao-editar-${solicitacaoId}`).click();
    const form = page.getByTestId("solicitacao-form");
    const campo = form.getByTestId("campo-comprovante");
    await expect(campo).toContainText("reserva-pousada.pdf");

    await campo.getByRole("button", { name: "Retirar reserva-pousada.pdf" }).click();
    // Obrigatório: sem arquivo, não salva.
    await page.getByTestId("solicitacao-salvar").click();
    await expect(campo).toContainText("Campo obrigatório.");

    const envio = page.waitForResponse((r) => r.url().includes("/documentos/confirm/"));
    await form.locator("#campo-comprovante").setInputFiles(pdf("reserva-corrigida.pdf"));
    expect((await envio).status()).toBe(201);
    const edicao = page.waitForResponse(
      (r) => r.url().includes(`/solicitacoes/${solicitacaoId}/`) && r.request().method() === "PATCH",
    );
    // Depois de salvar, a montagem relê os documentos da demanda: vale a primeira leitura após o PATCH.
    let editado = false;
    void edicao.then(() => (editado = true));
    const releitura = page.waitForResponse(
      (r) =>
        editado &&
        r.url().endsWith(`/sgd/demandas/${fx.demanda.id}/documentos/`) &&
        r.request().method() === "GET",
    );
    await page.getByTestId("solicitacao-salvar").click();
    expect((await edicao).status()).toBe(200);

    await expect(page.getByTestId(`anexos-solicitacao-${solicitacaoId}`)).toContainText("reserva-corrigida.pdf");
    // O backend remove o anexo que deixou de ser citado: só o novo segue ativo na demanda.
    const ativos = ((await (await releitura).json()) as { tipo: string; nome_original: string }[])
      .filter((d) => d.tipo === "anexo")
      .map((d) => d.nome_original);
    expect(ativos).toEqual(["reserva-corrigida.pdf"]);
  });
});

test.describe("Super Admin — tipo em uso", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("com solicitação, não pode ser removido; desativado, fica Inativo", async ({ page }) => {
    await page.goto(TELA);
    await page.getByTestId("tipo-remover-hospedagem").click();
    await page.getByRole("button", { name: "Confirmar" }).click();
    await expect(page.getByText("Este tipo já tem solicitações e não pode ser removido. Desative-o.")).toBeVisible();
    await expect(page.getByTestId("tipo-hospedagem")).toBeVisible();

    await page.getByTestId("tipo-situacao-hospedagem").click();
    await page.getByTestId("situacao-confirmar").click();
    await expect(page.getByText(`Tipo desativado. A alteração ${AVISO}`)).toBeVisible();
    await expect(page.getByTestId("tipo-hospedagem")).toContainText("Inativo");
  });
});

test.describe("ADT — tipo desativado", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("o tipo inativo some do formulário de solicitação", async ({ page }) => {
    await abrirNovaSolicitacao(page);
    await page.locator("button#solicitacao-tipo").click();
    await expect(page.getByRole("option", { name: "Diárias", exact: true })).toBeVisible();
    await expect(page.getByRole("option", { name: "Hospedagem", exact: true })).toHaveCount(0);
  });
});

for (const perfil of ["ugp", "adt"] as const) {
  test.describe(`Perfil ${perfil}`, () => {
    test.use({ storageState: storageStatePath(perfil) });

    test("não acessa a tela nem vê Configurações no menu", async ({ page }) => {
      await page.goto(TELA);
      await expect(page.getByText("Conteúdo restrito")).toBeVisible();
      await expect(page.getByTestId("tipos-tabela")).toHaveCount(0);
      await expect(page.getByRole("link", { name: "Configurações" })).toHaveCount(0);
    });
  });
}
