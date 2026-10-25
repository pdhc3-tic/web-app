import { expect, test, type Browser, type Page } from "@playwright/test";
import {
  criarCicloDemandaFixture,
  PREFIXO_317,
  removerCicloDemandaFixture,
  type CicloDemandaFixture,
} from "./helpers/cicloDemandaFixture";
import { storageStatePath, type UserKey } from "./helpers/users";

/**
 * #317 (SGD-FE-6) — Ciclo de vida completo da demanda, através dos quatro
 * perfis, tudo pela tela e contra o backend real.
 *
 * Cada teste é uma jornada inteira: o ADT cria e submete, e cada perfil age
 * na sua sessão (um contexto do navegador por perfil). A fixture só cria as
 * atividades e a verba; nenhuma demanda nasce pronta.
 *
 * O bloqueio de saldo pelas duas travas é coberto em `montar-demanda.spec.ts`
 * (#295) — ver `docs/e2e-cobertura-sgd.md`.
 */

let fx: CicloDemandaFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarCicloDemandaFixture();
});

test.afterAll(() => {
  if (fx) removerCicloDemandaFixture(fx);
});

/** Abre uma página na sessão do perfil. Fechar o contexto é do chamador. */
async function comoPerfil(browser: Browser, perfil: UserKey): Promise<Page> {
  const contexto = await browser.newContext({ storageState: storageStatePath(perfil) });
  return contexto.newPage();
}

async function fechar(...paginas: Page[]) {
  await Promise.all(paginas.map((p) => p.context().close()));
}

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

const painel = (page: Page) => page.getByTestId("demanda-painel");

async function abrirNoPainel(page: Page, demandaId: number) {
  await page.goto(`/sgd/demandas?visao=todas&demanda=${demandaId}`);
  await expect(painel(page).getByTestId("painel-solicitacoes")).toBeVisible();
}

/** Preenche a solicitação de alimentação no formulário já aberto e salva. */
async function preencherAlimentacao(page: Page, pessoas: string, valorEmCentavos: string) {
  const form = page.getByTestId("solicitacao-form");
  await escolher(page, "campo-tipo_refeicao", "Almoço");
  await form.getByLabel("Número de pessoas").fill(pessoas);
  await form.getByLabel("Data e horário do serviço").fill("2026-11-20T12:00");
  await form.getByLabel("Valor estimado").fill(valorEmCentavos);
  await page.getByTestId("solicitacao-salvar").click();
  await expect(form).toHaveCount(0);
}

/** Submete pela tela de montagem; ela leva de volta ao painel da demanda. */
async function submeter(page: Page, demandaId: number) {
  await page.getByTestId("demanda-submeter").click();
  await page.waitForURL(new RegExp(`/sgd/demandas\\?demanda=${demandaId}$`));
  await expect(painel(page)).toContainText("Submetida");
}

/**
 * ADT: pela aba Demandas da ficha da atividade, cria a demanda, adiciona uma
 * solicitação de alimentação vendo o saldo das duas travas, e submete.
 * Devolve o id da demanda criada.
 */
async function criarESubmeter(
  page: Page,
  atividadeId: number,
  titulo: string,
  valorEmCentavos: string,
): Promise<number> {
  await page.goto(`/sgp/atividades/${atividadeId}?tab=demandas`);
  await page.getByTestId("demanda-nova-btn").click();
  await page.getByLabel("Título da demanda").fill(titulo);
  await page.getByTestId("nova-demanda-salvar").click();

  await page.waitForURL(/\/sgd\/demandas\/\d+\/editar$/);
  const demandaId = Number(/\/sgd\/demandas\/(\d+)\/editar$/.exec(page.url())![1]);
  await expect(page.getByTestId("montar-demanda")).toContainText("Rascunho");

  await page.getByTestId("solicitacao-adicionar").click();
  await escolher(page, "solicitacao-tipo", "Alimentação");
  // O saldo aparece antes de salvar, nas duas travas.
  await expect(page.getByTestId("saldo-individual")).toContainText("Disponível");
  await expect(page.getByTestId("saldo-territorial")).toContainText("Disponível");
  await preencherAlimentacao(page, "40", valorEmCentavos);

  await submeter(page, demandaId);
  return demandaId;
}

/** Articulador Estadual: a demanda está na sua fila, e ele pré-autoriza. */
async function preAutorizar(page: Page, demandaId: number) {
  await page.goto("/sgd/demandas");
  await page.getByTestId(`demanda-linha-${demandaId}`).getByRole("button").click();
  await expect(painel(page).getByTestId("painel-solicitacoes")).toBeVisible();
  await painel(page).getByTestId("acao-pre-autorizar").click();
  await expect(painel(page).getByTestId("decisao-preview")).toBeVisible();
  await painel(page).getByTestId("decisao-confirmar").click();
  await expect(painel(page).getByTestId("painel-mensagem-sucesso")).toContainText("pré-autorizada");
}

/**
 * Lê o "Disponível" das duas travas no formulário de solicitação da demanda
 * em Rascunho da fixture, para o valor dado. Fecha o formulário sem salvar.
 */
async function lerSaldo(page: Page, valorEmCentavos: string) {
  await page.goto(`/sgd/demandas/${fx.consultaSaldo.id}/editar`);
  await page.getByTestId("solicitacao-adicionar").click();
  await escolher(page, "solicitacao-tipo", "Alimentação");
  await page.getByTestId("solicitacao-form").getByLabel("Valor estimado").fill(valorEmCentavos);
  const saldo = page.getByTestId("saldo-solicitacao");
  // O valor só vai à consulta depois do debounce: espera a resposta do valor digitado.
  await expect(saldo).toContainText("Disponível");
  const individual = await page.getByTestId("saldo-individual").locator("strong").innerText();
  const territorial = await page.getByTestId("saldo-territorial").locator("strong").innerText();
  return { individual, territorial };
}

test.describe("SGD — ciclo de vida da demanda", () => {
  test("caminho feliz: criada, submetida, pré-autorizada, autorizada, atendida e concluída com valor pago", async ({
    browser,
  }) => {
    const [adt, articulador, ugp, fgd] = await Promise.all(
      (["adt", "articuladorPB", "ugp", "fgd"] as const).map((p) => comoPerfil(browser, p)),
    );
    const titulo = `${PREFIXO_317} Almoço da feira agroecológica`;

    const id = await criarESubmeter(adt, fx.feliz.id, titulo, "120000");

    await preAutorizar(articulador, id);
    await expect(painel(articulador)).toContainText("Pré-autorizada");

    // UGP: autoriza como pedido, depois de o impacto no saldo ser validado.
    await ugp.goto("/sgd/demandas");
    await ugp.getByTestId(`demanda-linha-${id}`).getByRole("button").click();
    await painel(ugp).getByTestId("acao-autorizar").click();
    await expect(painel(ugp).getByTestId("decisao-preview")).toBeVisible();
    await expect(painel(ugp).getByTestId("decisao-confirmar")).toBeEnabled();
    await painel(ugp).getByTestId("decisao-confirmar").click();
    await expect(painel(ugp).getByTestId("painel-mensagem-sucesso")).toContainText("autorizada");
    await expect(painel(ugp)).toContainText("Autorizada");

    // FGD: a demanda está na sua fila; inicia o atendimento e conclui.
    await fgd.goto("/sgd/demandas");
    await fgd.getByTestId(`demanda-linha-${id}`).getByRole("button").click();
    await painel(fgd).getByTestId("acao-atender").click();
    await expect(painel(fgd).getByTestId("painel-mensagem-sucesso")).toContainText("Atendimento iniciado");
    await painel(fgd).getByTestId("acao-concluir").click();
    await painel(fgd).getByLabel(/Valor pago/).fill("1150");
    await painel(fgd).getByTestId("decisao-confirmar").click();
    await expect(painel(fgd).getByTestId("painel-mensagem-sucesso")).toContainText("Demanda concluída");

    // O solicitante vê o desfecho e o caminho inteiro na linha do tempo.
    await abrirNoPainel(adt, id);
    await expect(painel(adt)).toContainText("Concluída");
    await expect(painel(adt)).toContainText("pago R$ 1.150,00");
    await painel(adt).getByRole("tab", { name: "Linha do tempo" }).click();
    const timeline = painel(adt).getByTestId("painel-timeline");
    await expect(timeline).toContainText("Pré-autorização: Aprovado");
    await expect(timeline).toContainText("Autorização: Aprovado");

    await fechar(adt, articulador, ugp, fgd);
  });

  test("devolução: o Articulador devolve com justificativa e o solicitante corrige e submete de novo", async ({
    browser,
  }) => {
    const [adt, articulador] = await Promise.all(
      (["adt", "articuladorPB"] as const).map((p) => comoPerfil(browser, p)),
    );
    const titulo = `${PREFIXO_317} Lanche da oficina de beneficiamento`;
    const motivo = "Informe o número de participantes confirmados.";

    const id = await criarESubmeter(adt, fx.devolucao.id, titulo, "90000");

    await articulador.goto("/sgd/demandas");
    await articulador.getByTestId(`demanda-linha-${id}`).getByRole("button").click();
    await painel(articulador).getByTestId("acao-devolver").click();
    // Sem justificativa, não devolve.
    await painel(articulador).getByTestId("decisao-confirmar").click();
    await expect(painel(articulador)).toContainText("Informe o motivo da devolução.");
    await painel(articulador).getByLabel("Motivo da devolução").fill(motivo);
    await painel(articulador).getByTestId("decisao-confirmar").click();
    await expect(painel(articulador).getByTestId("painel-mensagem-info")).toContainText("devolvida");

    // O solicitante vê a devolução e o motivo, e corrige a solicitação.
    await abrirNoPainel(adt, id);
    await expect(painel(adt)).toContainText("Devolvida");
    await painel(adt).getByRole("tab", { name: "Linha do tempo" }).click();
    await expect(painel(adt).getByTestId("painel-timeline")).toContainText(motivo);
    const corrigir = painel(adt).getByTestId("painel-montar-demanda");
    await expect(corrigir).toHaveText("Corrigir e submeter de novo");
    await corrigir.click();
    await expect(adt.getByTestId("montar-demanda")).toContainText("Devolvida");

    const cartao = adt.getByTestId("montar-solicitacoes").locator("li").first();
    await cartao.locator('[data-testid^="solicitacao-editar-"]').click();
    await adt.getByTestId("solicitacao-form").getByLabel("Número de pessoas").fill("35");
    await adt.getByTestId("solicitacao-salvar").click();
    await expect(adt.getByTestId("solicitacao-form")).toHaveCount(0);
    await expect(cartao).toContainText("35");

    await submeter(adt, id);

    // De volta à fila do Articulador, como Submetida.
    await articulador.goto("/sgd/demandas");
    await expect(articulador.getByTestId(`demanda-linha-${id}`)).toContainText("Submetida");

    await fechar(adt, articulador);
  });

  test("recusa: a UGP só recusa com justificativa, e o solicitante vê o motivo", async ({ browser }) => {
    const [adt, articulador, ugp] = await Promise.all(
      (["adt", "articuladorPB", "ugp"] as const).map((p) => comoPerfil(browser, p)),
    );
    const titulo = `${PREFIXO_317} Café do encontro de mulheres rurais`;
    const justificativa = "Já há uma demanda autorizada para a mesma refeição.";

    const id = await criarESubmeter(adt, fx.recusa.id, titulo, "70000");
    await preAutorizar(articulador, id);

    await ugp.goto("/sgd/demandas");
    await ugp.getByTestId(`demanda-linha-${id}`).getByRole("button").click();
    await painel(ugp).getByTestId("acao-recusar").click();
    const drawer = ugp.getByTestId("recusar-drawer");
    await ugp.getByTestId("recusar-drawer-confirmar").click();
    await expect(drawer).toContainText("A justificativa é obrigatória.");
    await drawer.getByLabel("Justificativa da recusa").fill(justificativa);
    await ugp.getByTestId("recusar-drawer-confirmar").click();
    await expect(painel(ugp).getByTestId("painel-mensagem-info")).toContainText("recusada");

    await abrirNoPainel(adt, id);
    await expect(painel(adt)).toContainText("Recusada");
    await expect(painel(adt).getByTestId("painel-montar-demanda")).toHaveCount(0);
    await painel(adt).getByRole("tab", { name: "Linha do tempo" }).click();
    await expect(painel(adt).getByTestId("painel-timeline")).toContainText(justificativa);

    await fechar(adt, articulador, ugp);
  });

  test("cancelamento automático: cancelada a atividade, a demanda é cancelada e o saldo volta", async ({
    browser,
  }) => {
    const adt = await comoPerfil(browser, "adt");
    const titulo = `${PREFIXO_317} Almoço do dia de campo`;

    const id = await criarESubmeter(adt, fx.cancelamento.id, titulo, "80000");
    const antes = await lerSaldo(adt, "100");

    // Cancela a atividade pela ficha, com a justificativa obrigatória.
    await adt.goto(`/sgp/atividades/${fx.cancelamento.id}/`);
    await adt.getByTestId("atividade-status-btn").click();
    const dialogo = adt.getByTestId("transicao-dialog");
    await dialogo.getByTestId("transicao-destino").locator('button[role="combobox"]').click();
    await dialogo.locator('[role="option"]').filter({ hasText: /^Cancelada$/ }).first().click();
    await dialogo
      .getByTestId("transicao-justificativa")
      .locator("textarea")
      .fill("Dia de campo cancelado pela chuva na comunidade.");
    await adt.getByTestId("transicao-confirmar").click();
    await expect(dialogo).toHaveCount(0);

    // O cancelamento da demanda é assíncrono (task do Celery depois do
    // commit): recarrega até o status mudar, sem espera fixa.
    await expect(async () => {
      await abrirNoPainel(adt, id);
      await expect(painel(adt)).toContainText("Cancelada", { timeout: 2_000 });
    }).toPass({ timeout: 30_000 });

    // Os R$ 800 reservados na submissão voltam às duas travas.
    const depois = await lerSaldo(adt, "100");
    const real = (s: string) => Number(s.replace(/[^\d,]/g, "").replace(",", "."));
    expect(real(depois.individual) - real(antes.individual)).toBeCloseTo(800, 2);
    expect(real(depois.territorial) - real(antes.territorial)).toBeCloseTo(800, 2);

    await fechar(adt);
  });
});
