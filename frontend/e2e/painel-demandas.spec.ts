import { expect, test, type Page } from "@playwright/test";
import {
  criarPainelDemandasFixture,
  removerPainelDemandasFixture,
  type PainelDemandasFixture,
} from "./helpers/painelDemandasFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #296 — Painel master-detail de Demandas + decisões por perfil (SGD).
 *
 * Contra o backend real: a fixture leva cada demanda ao status pelos services
 * do SGD, com reservas de saldo de verdade.
 */

let fx: PainelDemandasFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarPainelDemandasFixture();
});

test.afterAll(() => {
  removerPainelDemandasFixture();
});

const linha = (page: Page, id: number) => page.getByTestId(`demanda-linha-${id}`);
const painel = (page: Page) => page.getByTestId("demanda-painel");

async function abrirDemanda(page: Page, id: number) {
  await linha(page, id).getByRole("button").click();
  await expect(page).toHaveURL(new RegExp(`demanda=${id}`));
  await expect(painel(page).getByTestId("painel-solicitacoes")).toBeVisible();
}

test.describe("Articulador Estadual (atua em RN)", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("o badge da sidebar mostra quantas demandas aguardam a sua ação", async ({ page }) => {
    await page.goto("/sgd/demandas");
    await expect(linha(page, fx.preAutorizar.id)).toBeVisible();
    const n = await page.getByTestId("demandas-tabela").locator("tbody tr").count();
    // As duas Submetidas da fixture estão na fila do Articulador de RN.
    expect(n).toBeGreaterThanOrEqual(2);
    const badge = page.getByTestId("sidebar-badge-sgd");
    await expect(badge).toHaveText(String(n));
    await expect(badge).toHaveAttribute("aria-label", `${n} pendente${n === 1 ? "" : "s"}`);
  });

  test("a tela do SGD mostra a mesma contagem no card do painel", async ({ page }) => {
    await page.goto("/sgd/demandas");
    await expect(linha(page, fx.preAutorizar.id)).toBeVisible();
    const n = await page.getByTestId("demandas-tabela").locator("tbody tr").count();

    await page.goto("/sgd");
    await expect(page.getByTestId("sgd-painel")).toContainText(String(n));
    // Articulador não abre demanda: o card de criação não aparece.
    await expect(page.getByTestId("sgd-nova")).toHaveCount(0);

    await page.getByTestId("sgd-painel").click();
    await expect(page).toHaveURL(/\/sgd\/demandas\/?$/);
  });

  test("pré-autoriza uma Submetida do seu estado e ela sai da fila", async ({ page }) => {
    await page.goto("/sgd/demandas");
    await expect(page.getByTestId("demandas-visao-minha")).toHaveAttribute("aria-selected", "true");
    await expect(linha(page, fx.preAutorizar.id)).toBeVisible();

    await abrirDemanda(page, fx.preAutorizar.id);
    // Painel aberto: só Título, Status e Solicitante na lista.
    await expect(page.getByTestId("demandas-tabela").getByRole("columnheader")).toHaveText([
      "Título",
      "Status",
      "Solicitante",
    ]);

    await painel(page).getByTestId("acao-pre-autorizar").click();
    await expect(painel(page).getByTestId("decisao-preview")).toBeVisible();
    await painel(page).getByTestId("decisao-confirmar").click();

    await expect(painel(page).getByTestId("painel-mensagem-sucesso")).toContainText(
      "pré-autorizada",
    );
    await expect(painel(page)).toContainText("Pré-autorizada");
    await expect(linha(page, fx.preAutorizar.id)).toHaveCount(0);
    // A mesma consulta alimenta a fila e o badge: ele acompanha a decisão.
    const restantes = await page.getByTestId("demandas-tabela").locator("tbody tr").count();
    if (restantes > 0) {
      await expect(page.getByTestId("sidebar-badge-sgd")).toHaveText(String(restantes));
    } else {
      await expect(page.getByTestId("sidebar-badge-sgd")).toHaveCount(0);
    }
  });

  test("devolver exige justificativa e devolve a demanda ao solicitante", async ({ page }) => {
    await page.goto(`/sgd/demandas?demanda=${fx.devolver.id}`);
    await painel(page).getByTestId("acao-devolver").click();

    await painel(page).getByTestId("decisao-confirmar").click();
    await expect(painel(page)).toContainText("Informe o motivo da devolução.");

    await painel(page).getByLabel("Motivo da devolução").fill("Falta o roteiro da viagem.");
    await painel(page).getByTestId("decisao-confirmar").click();

    await expect(painel(page).getByTestId("painel-mensagem-info")).toContainText("devolvida");
    await expect(painel(page)).toContainText("Devolvida");
  });

  test("a linha do tempo mostra a pré-autorização, com o responsável", async ({ page }) => {
    await page.goto(`/sgd/demandas?visao=todas&demanda=${fx.preAutorizar.id}`);
    await painel(page).getByRole("tab", { name: "Linha do tempo" }).click();
    const timeline = painel(page).getByTestId("painel-timeline");
    await expect(timeline).toContainText("Demanda criada");
    await expect(timeline).toContainText("Pré-autorização: Aprovado");
    await expect(timeline).toContainText("Hélio");
    // O solicitante aparece pelo nome, não mais pelo id.
    await expect(painel(page)).toContainText("Ewerton Bandeira");
  });
});

test.describe("Articulador Estadual de outro estado", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("não vê as demandas de RN, nem na fila nem em Todas", async ({ page }) => {
    await page.goto("/sgd/demandas?visao=todas");
    await expect(page.getByRole("heading", { name: "Demandas" })).toBeVisible();
    for (const d of [fx.autorizar, fx.recusar, fx.atender]) {
      await expect(page.getByText(d.titulo)).toHaveCount(0);
    }
  });

  test("abrir a URL direta de uma demanda de outro estado não revela a auditoria (#322)", async ({
    page,
  }) => {
    // Sem acesso à demanda, o detalhe responde 404 e o painel não abre as abas:
    // a aba "Auditoria" nunca aparece para quem não enxerga a demanda.
    const detalhe = page.waitForResponse(
      (r) => r.url().includes(`/api/v1/sgd/demandas/${fx.auditada.id}/`) && r.request().method() === "GET",
    );
    await page.goto(`/sgd/demandas?demanda=${fx.auditada.id}`);
    expect((await detalhe).status()).toBe(404);
    await expect(page.getByRole("heading", { name: "Demandas" })).toBeVisible();
    await expect(painel(page).getByRole("tab")).toHaveCount(0);
    await expect(painel(page).getByTestId("painel-auditoria")).toHaveCount(0);
  });
});

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a confirmação só libera quando o impacto no saldo foi validado", async ({ page }) => {
    const CORS = { "access-control-allow-origin": "*" };
    let modo: "segurar" | "sem-saldo" | "erro" | "real" = "segurar";
    let liberar: () => void = () => {};
    const segurando = new Promise<void>((r) => (liberar = r));

    await page.route(
      (url) => url.pathname.endsWith("/preview-decisao/"),
      async (route) => {
        if (route.request().method() === "OPTIONS" || modo === "real") return route.fallback();
        if (modo === "erro") {
          return route.fulfill({ status: 500, headers: CORS, body: "erro" });
        }
        if (modo === "segurar") await segurando;
        const trava = { semaforo_antes: "verde", semaforo_apos: "vermelho", saldo_apos: -100 };
        await route.fulfill({
          status: 200,
          headers: { ...CORS, "content-type": "application/json" },
          body: JSON.stringify({
            disponivel: false,
            trava_bloqueada: "individual",
            individual: trava,
            territorial: { ...trava, semaforo_apos: "verde", saldo_apos: 1000 },
          }),
        });
      },
    );

    await page.goto(`/sgd/demandas?demanda=${fx.autorizar.id}`);
    await painel(page).getByTestId("acao-ajustar").click();
    const confirmar = painel(page).getByTestId("decisao-confirmar");
    const bloqueio = painel(page).getByTestId("decisao-bloqueio");

    // 1. Calculando: a resposta ainda não chegou.
    await painel(page).getByLabel(/Valor autorizado/).fill("9000");
    await expect(bloqueio).toContainText("Calculando o impacto");
    await expect(confirmar).toBeDisabled();

    // 2. O impacto chegou, mas sem saldo.
    modo = "sem-saldo";
    liberar();
    await expect(bloqueio).toContainText("excede o saldo");
    await expect(confirmar).toBeDisabled();

    // 3. O cálculo falhou: bloqueado, com a opção de calcular de novo.
    modo = "erro";
    await painel(page).getByLabel(/Valor autorizado/).fill("9100");
    await expect(bloqueio).toContainText("Não foi possível calcular");
    await expect(painel(page).getByRole("button", { name: "Calcular de novo" })).toBeVisible();
    await expect(confirmar).toBeDisabled();

    // 4. Impacto real, com saldo: libera.
    modo = "real";
    await painel(page).getByLabel(/Valor autorizado/).fill("1300");
    await expect(bloqueio).toHaveCount(0);
    await expect(confirmar).toBeEnabled();

    await painel(page).getByRole("button", { name: "Voltar" }).click();
  });

  test("autoriza com valor ajustado vendo o preview mudar de faixa", async ({ page }) => {
    await page.goto("/sgd/demandas");
    await expect(linha(page, fx.autorizar.id)).toBeVisible();
    await abrirDemanda(page, fx.autorizar.id);

    await painel(page).getByTestId("acao-ajustar").click();
    await painel(page).getByLabel(/Valor autorizado/).fill("3000");

    const preview = painel(page).getByTestId(`preview-${fx.autorizar.solicitacaoId}`);
    await expect(preview.getByTestId("preview-mudanca-faixa")).toBeVisible();
    await expect(preview.locator('[data-faixa="amarelo"]')).toBeVisible();

    await painel(page).getByTestId("decisao-confirmar").click();
    await expect(painel(page).getByTestId("painel-mensagem-sucesso")).toContainText("autorizada");
    await expect(painel(page)).toContainText("Autorizada");
  });

  test("recusar abre o drawer, exige justificativa e só confirma em “Recusar demanda”", async ({
    page,
  }) => {
    await page.goto(`/sgd/demandas?demanda=${fx.recusar.id}`);
    await painel(page).getByTestId("acao-recusar").click();

    const drawer = page.getByTestId("recusar-drawer");
    await expect(drawer).toBeVisible();
    await expect(page.getByRole("button", { name: "Manter demanda" })).toBeVisible();

    await page.getByTestId("recusar-drawer-confirmar").click();
    await expect(drawer).toContainText("A justificativa é obrigatória.");

    await drawer.getByLabel("Justificativa da recusa").fill("Pedido em duplicidade com outra demanda.");
    await page.getByTestId("recusar-drawer-confirmar").click();

    await expect(painel(page).getByTestId("painel-mensagem-info")).toContainText("recusada");
    await expect(painel(page)).toContainText("Recusada");
  });

  test("cancelar uma demanda autorizada pede justificativa no ConfirmationDrawer", async ({
    page,
  }) => {
    await page.goto(`/sgd/demandas?visao=todas&demanda=${fx.cancelar.id}`);
    await painel(page).getByTestId("acao-cancelar").click();

    const drawer = page.getByTestId("cancelar-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("já foi autorizada");

    await page.getByTestId("cancelar-drawer-confirmar").click();
    await expect(drawer).toContainText("A justificativa é obrigatória.");

    await drawer
      .getByLabel("Justificativa do cancelamento")
      .fill("A visita foi adiada para o próximo semestre.");
    await page.getByTestId("cancelar-drawer-confirmar").click();

    await expect(painel(page).getByTestId("painel-mensagem-info")).toContainText("cancelada");
    await expect(painel(page)).toContainText("Cancelada");
    await expect(painel(page).getByTestId("acao-cancelar")).toHaveCount(0);

    await painel(page).getByRole("tab", { name: "Linha do tempo" }).click();
    const timeline = painel(page).getByTestId("painel-timeline");
    await expect(timeline).toContainText("Cancelamento: Cancelado");
    await expect(timeline).toContainText("A visita foi adiada para o próximo semestre.");
  });
});

test.describe("FGD", () => {
  test.use({ storageState: storageStatePath("fgd") });

  test("a fila traz as Autorizadas, com o mesmo total do badge", async ({ page }) => {
    const listagem = page.waitForRequest(
      (req) => req.url().includes("/api/v1/sgd/demandas/?") && req.url().includes("aguardando"),
    );
    await page.goto("/sgd/demandas");
    const params = new URL((await listagem).url()).searchParams;
    expect(params.get("aguardando_minha_acao")).toBe("true");

    await expect(linha(page, fx.atender.id)).toBeVisible();
    const n = await page.getByTestId("demandas-tabela").locator("tbody tr").count();
    await expect(page.getByTestId("sidebar-badge-sgd")).toHaveText(String(n));
  });

  test("a FGD não cancela uma demanda autorizada", async ({ page }) => {
    await page.goto(`/sgd/demandas?demanda=${fx.atender.id}`);
    await expect(painel(page).getByTestId("acao-atender")).toBeVisible();
    await expect(painel(page).getByTestId("acao-cancelar")).toHaveCount(0);
  });

  test("inicia o atendimento e conclui em seguida, sem recarregar", async ({ page }) => {
    await page.goto(`/sgd/demandas?demanda=${fx.atender.id}`);
    await painel(page).getByTestId("acao-atender").click();
    await expect(painel(page).getByTestId("painel-mensagem-sucesso")).toContainText(
      "Atendimento iniciado",
    );
    await expect(painel(page)).toContainText("Em atendimento");
    await expect(painel(page).getByTestId("acao-concluir")).toBeVisible();

    // Logo em seguida: o painel já está no estado novo, sem esperar as listas
    // recarregarem (a corrida que desfazia o formulário do Concluir sozinho).
    await painel(page).getByTestId("acao-concluir").click();
    await expect(painel(page).getByTestId("painel-mensagem-sucesso")).toHaveCount(0);
    await painel(page).getByLabel(/Valor pago/).fill("1100");
    await painel(page).getByTestId("decisao-confirmar").click();
    await expect(painel(page).getByTestId("painel-mensagem-sucesso")).toContainText(
      "Demanda concluída",
    );
    await expect(painel(page)).toContainText("Concluída");
    await expect(painel(page)).toContainText("pago R$ 1.100,00");
  });

  test("a FGD não vê a aba Auditoria — ela é restrita ao Super Admin (#322)", async ({ page }) => {
    await page.goto(`/sgd/demandas?demanda=${fx.atender.id}`);
    await expect(painel(page).getByRole("tab", { name: "Linha do tempo" })).toBeVisible();
    await expect(painel(page).getByRole("tab", { name: "Auditoria" })).toHaveCount(0);
  });
});

/**
 * #322 — Aba de auditoria no painel master-detail, consumindo o endpoint
 * `GET /api/v1/sgd/demandas/{id}/auditoria/` (BE-7). O backend restringe a
 * trilha ao Super Admin porque devolve IP de origem (ver
 * `pendencias-backend-sprint-10.md`, item 19).
 */
test.describe("Super Admin — Auditoria da demanda (#322)", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  async function abrirAuditoria(page: Page, id: number) {
    await page.goto(`/sgd/demandas?visao=todas&demanda=${id}`);
    const aba = painel(page).getByRole("tab", { name: "Auditoria" });
    await expect(aba).toBeVisible();
    await aba.click();
    await expect(painel(page).getByTestId("painel-auditoria")).toBeVisible();
  }

  test("eventos em ordem cronológica, com usuário, timestamp e ação", async ({ page }) => {
    // `auditada` sai da fixture já percorrida: criada, submetida (reserva),
    // pré-autorizada, autorizada e cancelada pela UGP (liberação). O backend
    // ordena por timestamp e id.
    await abrirAuditoria(page, fx.auditada.id);
    const status = painel(page).locator("[data-tipo='status']");

    // Todas as transições, nesta ordem e sem outras no meio.
    await expect(status).toHaveText([
      /Demanda criada/,
      /Rascunho → Submetida/,
      /Submetida → Pré-autorizada/,
      /Pré-autorizada → Autorizada/,
      /Autorizada → Cancelada/,
    ]);

    // Quem agiu e quando: o ADT cria, a UGP cancela; timestamp DD/MM/AAAA HH:mm.
    await expect(status.first()).toContainText("Ewerton Bandeira");
    await expect(status.first()).toContainText(/\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/);
    await expect(status.last()).toContainText("Beatriz Nogueira");
  });

  test("diferenciação visual: ícone de status e ícone de saldo", async ({ page }) => {
    await abrirAuditoria(page, fx.auditada.id);
    // A reserva de saldo entra na submissão; o cancelamento emite liberação.
    await expect(painel(page).locator("[data-tipo='status']").first()).toBeVisible();
    await expect(painel(page).locator("[data-tipo='saldo']").first()).toBeVisible();
  });

  test("'carregar mais' pede a próxima página do backend", async ({ page }) => {
    const CORS = { "access-control-allow-origin": "*" };
    const totalFake = 25;

    function evento(id: number, offset: number) {
      const tipo = id % 2 === 0 ? "status" : "saldo";
      const acao = tipo === "status" ? "demanda.status_alterado" : "saldo.reserva";
      return {
        id,
        tipo,
        acao,
        usuario: { id: 1, nome: "Vera Lucena" },
        ip: "203.0.113.9",
        timestamp: new Date(Date.UTC(2026, 9, 1, 12, offset)).toISOString(),
        valores_anteriores: tipo === "status" ? { status: "submetida" } : {},
        valores_novos: tipo === "status" ? { status: "pre_autorizada" } : { valor: "100.00" },
      };
    }

    await page.route(
      (url) => /\/api\/v1\/sgd\/demandas\/\d+\/auditoria\/?/.test(url.pathname),
      async (route) => {
        if (route.request().method() === "OPTIONS") return route.fallback();
        const params = new URL(route.request().url()).searchParams;
        const limit = Number(params.get("limit") ?? 20);
        const offset = Number(params.get("offset") ?? 0);
        const paginaIds = Array.from({ length: Math.min(limit, totalFake - offset) }, (_, i) =>
          evento(offset + i + 1, offset + i),
        );
        const temProxima = offset + paginaIds.length < totalFake;
        await route.fulfill({
          status: 200,
          headers: { ...CORS, "content-type": "application/json" },
          body: JSON.stringify({
            count: totalFake,
            next: temProxima ? `?limit=${limit}&offset=${offset + limit}` : null,
            previous: null,
            results: paginaIds,
          }),
        });
      },
    );

    await abrirAuditoria(page, fx.cancelar.id);
    const eventos = painel(page).locator("[data-testid^='auditoria-evento-']");
    await expect(eventos).toHaveCount(20);

    const botao = painel(page).getByTestId("auditoria-carregar-mais");
    await expect(botao).toContainText("20 de 25");
    await botao.click();

    await expect(eventos).toHaveCount(25);
    await expect(painel(page).getByTestId("auditoria-carregar-mais")).toHaveCount(0);
  });

});

test.describe("UGP — sem acesso à auditoria (#322)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("vê a demanda, mas não a aba Auditoria, e o backend recusa a trilha", async ({ page }) => {
    // A UGP enxerga a demanda, mas a trilha é só do Super Admin (pendência 19):
    // além de a aba não aparecer, a rota responde 403 mesmo chamada direto.
    const doDetalhe = page.waitForRequest((r) =>
      r.url().includes(`/api/v1/sgd/demandas/${fx.auditada.id}/`),
    );
    await page.goto(`/sgd/demandas?visao=todas&demanda=${fx.auditada.id}`);
    const api = new URL((await doDetalhe).url()).origin;

    await expect(painel(page).getByRole("tab", { name: "Linha do tempo" })).toBeVisible();
    await expect(painel(page).getByRole("tab", { name: "Auditoria" })).toHaveCount(0);

    const status = await page.evaluate(
      async ({ api, id }) => {
        const sessao = await (await fetch("/api/auth/session")).json();
        const res = await fetch(`${api}/api/v1/sgd/demandas/${id}/auditoria/`, {
          headers: { Authorization: `Bearer ${sessao.accessToken}` },
        });
        return res.status;
      },
      { api, id: fx.auditada.id },
    );
    expect(status).toBe(403);
  });
});
