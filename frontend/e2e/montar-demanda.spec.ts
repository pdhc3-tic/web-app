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
 * O total das diárias em tempo real vem de `GET /sgd/config/diarias/simular/`
 * (SGD-REF-BE-12, #358); o calculado ao salvar também é conferido.
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
    // A quantidade e o valor vêm da regra do backend (#358: meia diária no dia
    // da volta, adicional de embarque), não de uma conta no teste.
    const simulacao = page.waitForResponse(
      (r) => r.url().includes("/sgd/config/diarias/simular/") && r.url().includes("data_fim=2026-11-12"),
    );
    await form.getByLabel("Data de ida").fill("2026-11-10");
    await form.getByLabel("Data de volta").fill("2026-11-12");
    const simulado = (await (await simulacao).json()) as { numero_diarias: string; valor_total: string };
    await form.getByLabel("Justificativa").fill("Facilitação do encontro.");

    // A diária não tem valor digitado: quem calcula é o backend.
    await expect(form.getByLabel("Valor estimado")).toHaveCount(0);
    await expect(page.getByTestId("saldo-individual")).toContainText("Disponível");
    await expect(page.getByTestId("saldo-territorial")).toBeVisible();

    await page.getByTestId("solicitacao-salvar").click();
    await expect(form).toHaveCount(0);

    // O calculado ao salvar é o mesmo da simulação, e a quantidade sai no
    // formato brasileiro ("2,5" com a meia diária).
    const total = Number(simulado.valor_total)
      .toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
      .replace(/\s/g, " ");
    const cartao = page.getByTestId("montar-solicitacoes").locator("li").first();
    await expect(cartao).toContainText("Diárias");
    const diarias = Number(simulado.numero_diarias).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
    await expect(cartao).toContainText(`Paulo Rocha · ${diarias} diária(s)`);
    await expect.poll(async () => ((await cartao.textContent()) ?? "").replace(/\s/g, " ")).toContain(total);
    await expect.poll(async () => ((await page.getByTestId("montar-total").textContent()) ?? "").replace(/\s/g, " ")).toBe(total);
  });

  test("diária: o total aparece em tempo real e muda com as datas", async ({ page }) => {
    await abrirMontagem(page, fx.vazia.id);
    await page.getByTestId("solicitacao-adicionar").click();
    const form = page.getByTestId("solicitacao-form");
    await escolher(page, "solicitacao-tipo", "Diárias");
    await page.getByTestId("campo-municipio_destino_id").fill(fx.municipioNome);
    await page.getByRole("option", { name: fx.municipioNome, exact: true }).click();

    // O esperado vem da própria rota (`GET /sgd/config/diarias/simular/`), com o token da sessão.
    const simulacao = page.waitForResponse((r) => r.url().includes("/api/v1/sgd/config/diarias/simular/"));
    await form.getByLabel("Data de ida").fill("2026-11-10");
    await form.getByLabel("Data de volta").fill("2026-11-12");
    const api = new URL((await simulacao).url()).origin;
    const valorTotal = (dataFim: string) =>
      page.evaluate(
        async ({ api, municipio, dataFim }) => {
          const sessao = await (await fetch("/api/auth/session")).json();
          const qs = new URLSearchParams({ municipio_destino_id: municipio, data_inicio: "2026-11-10", data_fim: dataFim });
          const res = await fetch(`${api}/api/v1/sgd/config/diarias/simular/?${qs}`, {
            headers: { Authorization: `Bearer ${sessao.accessToken}` },
          });
          return ((await res.json()) as { valor_total: string }).valor_total;
        },
        { api, municipio: String(fx.municipioId), dataFim },
      );
    const brl = (valor: string) =>
      Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }).replace(/\s/g, " ");
    const totalNaTela = () =>
      page.getByTestId("simulacao-diarias-total").textContent().then((t) => (t ?? "").replace(/\s/g, " "));

    const ate12 = await valorTotal("2026-11-12");
    await expect.poll(totalNaTela).toBe(brl(ate12));

    await form.getByLabel("Data de volta").fill("2026-11-14");
    const ate14 = await valorTotal("2026-11-14");
    expect(Number(ate14)).toBeGreaterThan(Number(ate12));
    await expect.poll(totalNaTela).toBe(brl(ate14));
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
    // Os valores vêm do INSUFFICIENT_BALANCE (#359): limite de R$ 5.000, passagem de R$ 6.000.
    await expect(page.getByTestId(`bloqueio-valores-${fx.multipla.passagemId}`)).toHaveText(
      "Disponível no seu limite: R$ 5.000,00 · Solicitado: R$ 6.000,00",
    );
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
    await expect(page.getByTestId("recurso-extra-bloqueio")).toHaveText(
      "Limite individual insuficiente: R$ 5.000,00 disponível, R$ 6.000,00 solicitado.",
    );
    // O que falta na rubrica vem em `valor_faltante`, antes de enviar (#321, #359).
    await expect(drawer).toContainText("R$ 1.000,00");
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
    // O solicitado é o que o backend calculou para a diária (tabela da #358).
    const solicitado = Number(fx.territorial.diariaValor)
      .toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
      .replace(/\s/g, " ");
    await expect
      .poll(async () =>
        ((await page.getByTestId(`bloqueio-valores-${fx.territorial.diariaId}`).textContent()) ?? "").replace(/\s/g, " "),
      )
      .toBe(`Disponível na verba do território: R$ 295,00 · Solicitado: ${solicitado}`);
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

test.describe("SGD — cotações em cache (#380)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("remover uma cotação não libera a submissão com a lista antiga do cache", async ({ page }) => {
    const chamadas: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/submeter/")) chamadas.push(r.url());
    });
    const id = fx.equipamentoCompleto.id;
    const listaDocumentos = (url: URL) => url.pathname === `/api/v1/sgd/demandas/${id}/documentos/`;
    const botao = page.getByTestId("demanda-submeter");
    const aviso = page.getByTestId("submissao-erro");

    await abrirMontagem(page, id);
    await expect(page.getByTestId("documentos-lista").locator("li")).toHaveCount(3);
    await expect(botao).toBeEnabled();

    // Removida a cotação, a lista não atualiza: a de 3 fica no cache.
    await page.route(listaDocumentos, (route) =>
      route.request().method() === "GET" ? route.abort() : route.fallback(),
    );
    await page.getByRole("button", { name: "Remover cotacao-Campo Verde.pdf" }).click();
    await page.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect(aviso).toContainText("Conferindo as cotações");
    await expect(botao).toBeDisabled();
    await expect(aviso).toContainText("Não foi possível conferir as cotações", { timeout: 20_000 });
    await expect(botao).toBeDisabled();

    // "Tentar de novo" traz a lista atual, com 2: continua barrado.
    await page.unroute(listaDocumentos);
    await page.getByTestId("submissao-recarregar-documentos").click();
    await expect(aviso).toContainText("ao menos 3 cotações");
    await expect(botao).toBeDisabled();

    // Anexada a terceira, com o GET atrasado: fica barrado até a lista chegar.
    await page.route(listaDocumentos, async (route) => {
      if (route.request().method() === "GET") await new Promise((r) => setTimeout(r, 1_500));
      await route.fallback();
    });
    await escolher(page, "documento-tipo", "Cotação");
    await page.getByLabel("Fornecedor").fill("Campo Verde");
    await page.locator("#documento-arquivo").setInputFiles({
      name: "cotacao-campo-verde.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"),
    });
    await page.getByTestId("documento-anexar").click();
    await expect(aviso).toContainText("Conferindo as cotações");
    await expect(botao).toBeDisabled();
    await expect(botao).toBeEnabled();
    expect(chamadas).toHaveLength(0);
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
