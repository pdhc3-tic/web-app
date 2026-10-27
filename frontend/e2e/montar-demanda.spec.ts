import { expect, test, type Page } from "@playwright/test";
import {
  criarMontarDemandaFixture,
  decidirRecursoExtra,
  removerMontarDemandaFixture,
  type MontarDemandaFixture,
} from "./helpers/montarDemandaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Montar e submeter a demanda (Issue #295), contra o backend real: o
 * formulário de cada tipo, o saldo antes de submeter, os bloqueios das duas
 * travas, o atalho do recurso extra (#321) e as cotações de equipamentos.
 *
 * O total das diárias em tempo real depende de `GET /sgd/config/diarias/simular/`,
 * que o backend ainda não publica (pendencias-backend-sprint-10.md, item 27):
 * fica `fixme`. O total calculado pelo backend ao salvar é coberto.
 */

let fx: MontarDemandaFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarMontarDemandaFixture();
});

test.afterAll(() => {
  removerMontarDemandaFixture(fx);
});

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

async function abrirMontagem(page: Page, demandaId: number) {
  await page.goto(`/sgd/demandas/${demandaId}/editar`);
  await expect(page.getByTestId("montar-demanda")).toBeVisible();
}

async function submeter(page: Page) {
  const resposta = page.waitForResponse((r) => r.url().includes("/submeter/"));
  await page.getByTestId("demanda-submeter").click();
  return resposta;
}

test.describe("SGD — montar e submeter a demanda (ADT)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("diária: os campos do tipo, o saldo antes de salvar e o total calculado pelo sistema", async ({
    page,
  }) => {
    await abrirMontagem(page, fx.vazia.id);
    await page.getByTestId("solicitacao-adicionar").click();
    const form = page.getByTestId("solicitacao-form");
    await escolher(page, "solicitacao-tipo", "Diárias");

    await form.getByLabel("Nome do beneficiário").fill("Paulo Rocha");
    await form.getByLabel("CPF do beneficiário").fill("52998224725");
    await expect(form.getByLabel("CPF do beneficiário")).toHaveValue("529.982.247-25");
    await form.getByLabel("Cargo ou função").fill("Facilitador");
    await escolher(page, "campo-beneficiario_vinculo", "Colaborador externo");
    await escolher(page, "campo-meio_transporte", "Rodoviário");
    await page.getByTestId("campo-municipio_destino_id").fill(fx.municipioNome);
    await page.getByRole("option", { name: fx.municipioNome, exact: true }).click();
    await form.getByLabel("Data de ida").fill("2026-11-10");
    await form.getByLabel("Data de volta").fill("2026-11-12");
    await form.getByLabel("Justificativa").fill("Facilitação do encontro.");

    // A diária não tem valor digitado: quem calcula é o backend.
    await expect(form.getByLabel("Valor estimado")).toHaveCount(0);
    await expect(page.getByTestId("saldo-individual")).toContainText("Disponível");
    await expect(page.getByTestId("saldo-territorial")).toBeVisible();

    await page.getByTestId("solicitacao-salvar").click();
    await expect(form).toHaveCount(0);

    // 2 diárias × R$ 300,00 (valor de teste do seed).
    const cartao = page.getByTestId("montar-solicitacoes").locator("li").first();
    await expect(cartao).toContainText("Diárias");
    await expect(cartao).toContainText("Paulo Rocha · 2 diária(s)");
    await expect(cartao).toContainText("R$ 600,00");
    await expect(page.getByTestId("montar-total")).toHaveText("R$ 600,00");
  });

  test.fixme("diária: o total aparece em tempo real e muda com as datas", async () => {
    // Depende de GET /sgd/config/diarias/simular/ (pendência 27, SGD-REF-BE-12 #358).
  });

  test("passagem: com ida e volta = Sim aparecem os campos da volta; com Não, somem", async ({ page }) => {
    await abrirMontagem(page, fx.vazia.id);
    await page.getByTestId("solicitacao-adicionar").click();
    const form = page.getByTestId("solicitacao-form");
    await escolher(page, "solicitacao-tipo", "Passagens Aéreas");

    const volta = form.getByLabel("Data e hora da volta");
    await expect(volta).toHaveCount(0);
    await form.getByTestId("campo-ida_e_volta").getByLabel("Sim").check();
    await expect(volta).toBeVisible();
    await form.getByTestId("campo-ida_e_volta").getByLabel("Não").check();
    await expect(volta).toHaveCount(0);

    // A classe executiva pede justificativa (§3.2).
    await expect(form.getByLabel("Justificativa da classe executiva")).toHaveCount(0);
    await escolher(page, "campo-classe", "Executiva");
    await expect(form.getByLabel("Justificativa da classe executiva")).toBeVisible();
  });

  test("submissão barrada pelo limite individual: mensagem e atalho; a outra solicitação segue no rascunho", async ({
    page,
  }) => {
    await abrirMontagem(page, fx.multipla.id);
    expect((await submeter(page)).status()).toBe(400);

    await expect(page.getByTestId("submissao-bloqueada")).toContainText("uma solicitação foi barrada");
    const bloqueio = page.getByTestId(`bloqueio-${fx.multipla.passagemId}`);
    await expect(bloqueio).toContainText("Limite individual insuficiente.");
    await expect(page.getByTestId(`recurso-extra-atalho-${fx.multipla.passagemId}`)).toBeVisible();
    // A de veículo coube: sem bloqueio, e continua lá.
    await expect(page.getByTestId(`bloqueio-${fx.multipla.veiculoId}`)).toHaveCount(0);

    await page.reload();
    await expect(page.getByTestId("montar-demanda")).toContainText("Rascunho");
    await expect(page.getByTestId(`solicitacao-${fx.multipla.passagemId}`)).toBeVisible();
    await expect(page.getByTestId(`solicitacao-${fx.multipla.veiculoId}`)).toBeVisible();
  });

  test("o atalho pede o recurso extra; aprovado o pedido, a demanda é submetida", async ({ page }) => {
    await abrirMontagem(page, fx.multipla.id);
    await submeter(page);
    await page.getByTestId(`recurso-extra-atalho-${fx.multipla.passagemId}`).click();

    const drawer = page.getByTestId("recurso-extra-drawer");
    await expect(drawer).toContainText("Passagens Aéreas");
    await drawer.getByLabel("Justificativa").fill("A caravana precisa da passagem da facilitadora.");
    await page.getByTestId("recurso-extra-revisar").click();
    await page.getByTestId("recurso-extra-enviar").click();
    await expect(page.getByTestId("recurso-extra-enviado")).toBeVisible();

    decidirRecursoExtra(fx.multipla.id, "aprovar");

    await abrirMontagem(page, fx.multipla.id);
    await expect(page.getByTestId("aviso-recurso-extra-aprovado")).toBeVisible();
    expect((await submeter(page)).status()).toBe(200);
    await page.waitForURL(`**/sgd/demandas?demanda=${fx.multipla.id}`);
    await expect(page.getByTestId("demanda-painel")).toContainText("Submetida");
  });

  test("recusado o pedido, a submissão continua barrada com a mensagem original", async ({ page }) => {
    await abrirMontagem(page, fx.recusada.id);
    expect((await submeter(page)).status()).toBe(400);
    await expect(page.getByTestId(`bloqueio-${fx.recusada.veiculoId}`)).toContainText(
      "Limite individual insuficiente.",
    );
    await expect(page.getByTestId(`recurso-extra-atalho-${fx.recusada.veiculoId}`)).toBeVisible();
  });

  test("submissão barrada pela verba do território orienta acionar o Articulador Estadual", async ({ page }) => {
    await abrirMontagem(page, fx.territorial.id);
    expect((await submeter(page)).status()).toBe(400);

    const bloqueio = page.getByTestId(`bloqueio-${fx.territorial.diariaId}`);
    await expect(bloqueio).toContainText("Verba do território insuficiente.");
    await expect(bloqueio).toContainText("Articulador Estadual");
    // A trava territorial não tem atalho: quem remaneja é o Articulador.
    await expect(page.getByTestId(`recurso-extra-atalho-${fx.territorial.diariaId}`)).toHaveCount(0);
  });

  test("equipamentos: sem a lista de documentos carregada, a submissão fica barrada", async ({ page }) => {
    const chamadas: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/submeter/")) chamadas.push(r.url());
    });
    // A lista de documentos falha: enquanto o React Query tenta de novo, a
    // regra está "conferindo"; esgotadas as tentativas, fica a falha.
    const listaDocumentos = (url: URL) => url.pathname === `/api/v1/sgd/demandas/${fx.equipamento.id}/documentos/`;
    await page.route(listaDocumentos, (route) =>
      route.request().method() === "GET" ? route.abort() : route.fallback(),
    );

    await abrirMontagem(page, fx.equipamento.id);
    await expect(page.getByTestId("submissao-erro")).toContainText("Conferindo as cotações");
    await expect(page.getByTestId("demanda-submeter")).toBeDisabled();
    await expect(page.getByTestId("submissao-erro")).toContainText("Não foi possível conferir as cotações", {
      timeout: 20_000,
    });
    await expect(page.getByTestId("demanda-submeter")).toBeDisabled();
    expect(chamadas).toHaveLength(0);

    // A lista volta: "Tentar de novo" carrega e a regra das cotações assume.
    await page.unroute(listaDocumentos);
    await page.getByTestId("submissao-recarregar-documentos").click();
    await expect(page.getByTestId("submissao-erro")).toContainText("ao menos 3 cotações");
    await expect(page.getByTestId("demanda-submeter")).toBeDisabled();
    expect(chamadas).toHaveLength(0);
  });

  test("equipamentos com menos de 3 cotações: barrado no cliente, sem chamar a API", async ({ page }) => {
    const chamadas: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/submeter/")) chamadas.push(r.url());
    });

    await abrirMontagem(page, fx.equipamento.id);
    await expect(page.getByTestId("documentos-lista").locator("li")).toHaveCount(2);
    await expect(page.getByTestId("submissao-erro")).toContainText("ao menos 3 cotações");
    await expect(page.getByTestId("demanda-submeter")).toBeDisabled();
    expect(chamadas).toHaveLength(0);

    // A terceira cotação, de outro fornecedor, libera a submissão.
    await escolher(page, "documento-tipo", "Cotação");
    await page.getByLabel("Fornecedor").fill("Campo Verde");
    await page.locator("#documento-arquivo").setInputFiles({
      name: "cotacao-campo-verde.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"),
    });
    await page.getByTestId("documento-anexar").click();
    await expect(page.getByTestId("documentos-lista").locator("li")).toHaveCount(3);
    await expect(page.getByTestId("submissao-erro")).toHaveCount(0);
    await expect(page.getByTestId("demanda-submeter")).toBeEnabled();

    expect((await submeter(page)).status()).toBe(200);
    await page.waitForURL(`**/sgd/demandas?demanda=${fx.equipamento.id}`);
  });
});

test.describe("SGD — montar demanda (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("só o solicitante monta a demanda", async ({ page }) => {
    await page.goto(`/sgd/demandas/${fx.vazia.id}/editar`);
    await expect(page.getByText("Conteúdo restrito")).toBeVisible();
    await expect(page.getByTestId("montar-demanda")).toHaveCount(0);
  });
});
