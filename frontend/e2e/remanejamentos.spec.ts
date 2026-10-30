import { expect, test, type Page } from "@playwright/test";
import {
  criarRemanejamentosFixture,
  removerRemanejamentosFixture,
  type RemanejamentosFixture,
} from "./helpers/remanejamentosFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #321 — Fluxo "Solicitar recurso extra" e Fila de Remanejamentos (SGD-FE-10).
 *
 * Contra o backend real (BE-12): a fixture cria os pedidos pelos services do
 * SGD, e o parecer do Articulador leva os da UGP a Com parecer.
 *
 * O atalho a partir do bloqueio na submissão e a ressubmissão depois da
 * decisão estão em `montar-demanda.spec.ts`, com a tela de submissão da #295.
 * O fluxo guiado em si é coberto no Vitest (`SolicitarRecursoExtra.test.tsx`).
 */

let fx: RemanejamentosFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarRemanejamentosFixture();
});

test.afterAll(() => {
  removerRemanejamentosFixture();
});

const linha = (page: Page, id: number) => page.getByTestId(`pedido-linha-${id}`);

async function abrirPedido(page: Page, id: number) {
  await page.goto("/sgd/remanejamentos");
  await linha(page, id).getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/sgd/remanejamentos/${id}`));
  await expect(page.getByTestId("pedido-acoes")).toBeVisible();
}

test.describe("Articulador Estadual (atua em RN)", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("a fila mostra os pedidos Submetidos; os Com parecer já saíram da sua etapa", async ({
    page,
  }) => {
    await page.goto("/sgd");
    await page.getByTestId("sgd-remanejamentos").click();
    await expect(page).toHaveURL(/\/sgd\/remanejamentos/);

    await expect(linha(page, fx.parecer.pedidoId)).toBeVisible();
    await expect(linha(page, fx.devolver.pedidoId)).toBeVisible();
    await expect(linha(page, fx.aprovar.pedidoId)).toHaveCount(0);

    await page.getByTestId("remanejamentos-visao-todos").click();
    await expect(linha(page, fx.aprovar.pedidoId)).toBeVisible();
  });

  test("emite parecer e o pedido segue para a UGP", async ({ page }) => {
    await abrirPedido(page, fx.parecer.pedidoId);
    await page.getByTestId("acao-parecer").click();
    await page.getByTestId("parecer-drawer").getByLabel("Parecer").fill("Favorável, sem ressalvas.");
    await page.getByTestId("parecer-drawer-confirmar").click();

    await expect(page.getByTestId("pedido-mensagem-sucesso")).toContainText("decisão da UGP");
    await expect(page.getByTestId("pedido-page")).toContainText("Com parecer");
    await expect(page.getByTestId("pedido-parecer")).toContainText("Favorável, sem ressalvas.");
    await expect(page.getByTestId("acao-parecer")).toHaveCount(0);
  });

  test("devolve ao solicitante com motivo obrigatório", async ({ page }) => {
    await abrirPedido(page, fx.devolver.pedidoId);
    await page.getByTestId("acao-devolver").click();
    await page.getByTestId("devolver-drawer-confirmar").click();
    await expect(page.getByTestId("devolver-drawer")).toContainText("A justificativa é obrigatória.");

    await page.getByTestId("devolver-drawer").getByLabel("Motivo da devolução").fill("Informe o roteiro da van.");
    await page.getByTestId("devolver-drawer-confirmar").click();

    await expect(page.getByTestId("pedido-mensagem-info")).toContainText("devolvido");
    await expect(page.getByTestId("pedido-page")).toContainText("Devolvida");
    await expect(page.getByTestId("pedido-parecer")).toContainText("Informe o roteiro da van.");
  });
});

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a fila lista os pedidos Com parecer, inclusive o do parecer recém-emitido", async ({ page }) => {
    await page.goto("/sgd/remanejamentos");
    await expect(linha(page, fx.aprovar.pedidoId)).toBeVisible();
    await expect(linha(page, fx.recusar.pedidoId)).toBeVisible();
    await expect(linha(page, fx.parecer.pedidoId)).toBeVisible();
    await expect(linha(page, fx.devolver.pedidoId)).toHaveCount(0);
  });

  test("recusa exige justificativa, e o pedido fica Recusado", async ({ page }) => {
    await abrirPedido(page, fx.recusar.pedidoId);
    await page.getByTestId("acao-recusar").click();
    await page.getByTestId("recusar-drawer-confirmar").click();
    await expect(page.getByTestId("recusar-drawer")).toContainText("A justificativa é obrigatória.");

    await page
      .getByTestId("recusar-drawer")
      .getByLabel("Justificativa da recusa")
      .fill("Demanda em duplicidade com outra já autorizada.");
    await page.getByTestId("recusar-drawer-confirmar").click();

    await expect(page.getByTestId("pedido-mensagem-info")).toContainText("continua bloqueada");
    await expect(page.getByTestId("pedido-decisao")).toContainText("Recusada");
    await expect(page.getByTestId("pedido-decisao")).toContainText("duplicidade");
    await expect(page.getByTestId("acao-aprovar")).toHaveCount(0);
  });

  test("aprova com justificativa e a tela diz que a demanda pode ser submetida de novo", async ({
    page,
  }) => {
    await abrirPedido(page, fx.aprovar.pedidoId);
    await page.getByTestId("acao-aprovar").click();
    const drawer = page.getByTestId("aprovar-drawer");
    await expect(drawer).toContainText("não é submetida sozinha");
    await drawer.getByLabel("Justificativa da aprovação").fill("Comitiva confirmada pela coordenação.");
    await page.getByTestId("aprovar-drawer-confirmar").click();

    await expect(page.getByTestId("pedido-mensagem-sucesso")).toContainText(
      "já pode ser submetida de novo",
    );
    await expect(page.getByTestId("pedido-decisao")).toContainText("Aprovada");
    await expect(page.getByTestId("pedido-page")).toContainText("Valor aprovado");
  });
});

test.describe("Solicitante (ADT de RN)", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("a demanda mostra que o recurso extra foi aprovado e pode ser submetida de novo", async ({
    page,
  }) => {
    await page.goto(`/sgd/demandas?visao=todas&demanda=${fx.aprovar.demandaId}`);
    const aviso = page.getByTestId("demanda-painel").getByTestId("aviso-recurso-extra-aprovado");
    await expect(aviso).toContainText("já pode ser submetida de novo");
    await expect(aviso).toContainText("R$ 200,00");
    await expect(aviso.getByRole("link")).toHaveAttribute(
      "href",
      `/sgd/remanejamentos/${fx.aprovar.pedidoId}`,
    );
  });

  test("cada demanda mostra o aviso do próprio pedido, não o do mais recente", async ({ page }) => {
    // O pedido mais recente do solicitante é o de `aprovar`. Com o filtro
    // ?demanda= do backend, a demanda de `recusar` mostra a recusa do pedido
    // dela, e não a aprovação do outro.
    const lista = page.waitForResponse(
      (r) => r.url().includes("/api/v1/sgd/remanejamentos/") && r.url().includes(`demanda=${fx.recusar.demandaId}`),
    );
    await page.goto(`/sgd/demandas?visao=todas&demanda=${fx.recusar.demandaId}`);
    await lista;
    const painel = page.getByTestId("demanda-painel");
    const aviso = painel.getByTestId("aviso-recurso-extra-recusado");
    await expect(aviso).toContainText("duplicidade");
    await expect(aviso.getByRole("link")).toHaveAttribute(
      "href",
      `/sgd/remanejamentos/${fx.recusar.pedidoId}`,
    );
    await expect(painel.getByTestId("aviso-recurso-extra-aprovado")).toHaveCount(0);
  });

  test("ajusta o pedido devolvido e reenvia ao Articulador", async ({ page }) => {
    await page.goto(`/sgd/remanejamentos/${fx.devolver.pedidoId}`);
    await expect(page.getByTestId("pedido-parecer")).toContainText("Informe o roteiro da van.");
    await page.getByLabel("Justificativa").fill("Roteiro: Natal → Mossoró, ida e volta em dois dias.");
    await page.getByTestId("acao-reenviar").click();

    await expect(page.getByTestId("pedido-mensagem-sucesso")).toContainText("reenviado");
    await expect(page.getByTestId("pedido-page")).toContainText("Submetida");
  });

  test("não acessa a Fila de Remanejamentos", async ({ page }) => {
    await page.goto("/sgd");
    await expect(page.getByTestId("sgd-painel")).toBeVisible();
    await expect(page.getByTestId("sgd-remanejamentos")).toHaveCount(0);

    await page.goto("/sgd/remanejamentos");
    await expect(page.getByText("Conteúdo restrito")).toBeVisible();
    await expect(page.getByTestId("remanejamentos-tabela")).toHaveCount(0);
  });
});

test.describe("FGD", () => {
  test.use({ storageState: storageStatePath("fgd") });

  test("não acessa a Fila de Remanejamentos", async ({ page }) => {
    await page.goto("/sgd/remanejamentos");
    await expect(page.getByText("Conteúdo restrito")).toBeVisible();
    await expect(page.getByTestId("remanejamentos-tabela")).toHaveCount(0);
  });
});
