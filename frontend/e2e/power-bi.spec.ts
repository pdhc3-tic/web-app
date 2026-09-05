import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Painel da integração Power BI (tela /admin/integracoes/power-bi, issue #143).
 *
 * ATENÇÃO — este é o único spec da suíte que faz uma escrita IRREVERSÍVEL.
 * Regenerar o token invalida o anterior de vez: o banco guarda só o hash
 * SHA-256 (`PowerBIToken.gerar`), então não existe `finally` capaz de repor o
 * valor antigo, como se faz em acessos-sca.spec.ts e google-calendar.spec.ts.
 *
 * Aceitável porque o dano é nulo: o token do ambiente de demonstração não é
 * usado por ninguém — `POWER_BI_SERVICE_TOKEN` está vazio no dev e nenhum
 * outro spec consome o endpoint do conector. O efeito colateral de rodar isto
 * é o banco ficar com um token ativo DIFERENTE do que o `seed_demo` tiver
 * criado; um `seed_demo --reset` devolve o estado semeado.
 *
 * O spec funciona nos dois cenários do seed — com token semeado (o botão diz
 * "Regenerar token") ou sem (diz "Gerar token"). Os testes que dependem de um
 * estado específico fixam a resposta com `page.route`.
 *
 * E é o preço de provar o critério de verdade: a issue aceitaria uma "chamada
 * simulada", mas com o token em claro na mão dá para bater no endpoint real da
 * BE-10 e ver o antigo passar a responder 401.
 */
const PAGE_URL = "/admin/integracoes/power-bi";

/** Endpoints admin (#215). O `$` separa o status da regeneração. */
const ADMIN_API = /\/api\/v1\/admin\/power-bi-token\/$/;
const REGENERAR_API = /\/api\/v1\/admin\/power-bi-token\/regenerar\/$/;

/**
 * O endpoint do conector (BE-10) é chamado FORA do navegador, pelo `request`
 * do Playwright: ele não usa a sessão da tela, e sim o token de serviço no
 * header `Authorization: Token <valor>` — exatamente como o Power BI faria.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BE10_URL = `${API_URL}/api/v1/sgp/plano-trabalho/powerbi/`;

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function abrir(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("power-bi-page")).toBeVisible();
  // O card do token só existe depois de o GET admin resolver no navegador —
  // esperá-lo garante dado em tela e React já hidratado.
  await expect(page.getByTestId("powerbi-token-card")).toBeVisible();
}

/**
 * O `NovoTokenDialog` dispara um `window.confirm` ao fechar sem que o token
 * tenha sido copiado, e o Playwright DISPENSA diálogos nativos por padrão — o
 * `confirm` voltaria `false` e o SlideOver não fecharia nunca. O teste copia
 * antes de fechar, e este handler é a rede de segurança para o caso de a área
 * de transferência falhar no ambiente. Registrado UMA vez por teste: dois
 * listeners tentariam tratar o mesmo diálogo.
 */
function aceitarConfirmacoes(page: Page): void {
  page.on("dialog", (dialog) => {
    void dialog.accept().catch(() => {});
  });
}

/** Percorre o fluxo de regeneração e devolve o token em claro do diálogo. */
async function regenerar(page: Page): Promise<string> {
  await page.getByTestId("powerbi-regenerar").click();
  await page.getByTestId("powerbi-regenerar-confirmar").click();

  const campo = page.getByTestId("powerbi-novo-token");
  await expect(campo).toBeVisible();
  const token = (await campo.innerText()).trim();

  // `secrets.token_urlsafe(32)` — 43 caracteres url-safe.
  expect(token).toMatch(/^[A-Za-z0-9_-]{40,}$/);

  const toast = page.getByTestId("toast");
  await expect(toast).toBeVisible();
  await expect(toast).toHaveAttribute("data-variant", "success");
  await expect(toast).toContainText("não será exibido novamente");

  await page.getByTestId("powerbi-novo-token-copiar").click();
  await page.getByTestId("powerbi-novo-token-fechar").click();
  await expect(campo).toHaveCount(0);

  return token;
}

const CONFIG_BASE = {
  url_endpoint: "/api/v1/sgp/plano-trabalho/powerbi/",
  token_mascarado: "••••3f2a",
  atualizado_em: new Date().toISOString(),
  status_snapshot: "em_dia",
};

async function stubConfig(
  page: Page,
  patch: Record<string, unknown> = {},
): Promise<void> {
  await page.route(ADMIN_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...CONFIG_BASE, ...patch }),
    });
  });
}

// ─── Regeneração de verdade ──────────────────────────────────────────────────

test.describe("Power BI — Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("regenerar exibe o token uma única vez e derruba o anterior", async ({
    page,
    context,
    request,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    aceitarConfirmacoes(page);
    await abrir(page);

    const primeiro = await regenerar(page);

    // Depois de fechar o diálogo, o valor em claro não sobrevive em lugar
    // nenhum da árvore — é o "uma única vez" do critério.
    expect(await page.locator("body").innerText()).not.toContain(primeiro);
    // E o card volta mascarado, mostrando só os últimos 4 caracteres.
    const mascarado = page.getByTestId("powerbi-token-mascarado");
    await expect(mascarado).toContainText("•");
    await expect(mascarado).toContainText(primeiro.slice(-4));

    // O token novo autentica no endpoint que o Power BI consome.
    const comNovo = await request.get(BE10_URL, {
      headers: { Authorization: `Token ${primeiro}` },
    });
    expect(comNovo.status()).toBe(200);

    const segundo = await regenerar(page);
    expect(segundo).not.toBe(primeiro);

    const comSegundo = await request.get(BE10_URL, {
      headers: { Authorization: `Token ${segundo}` },
    });
    expect(comSegundo.status()).toBe(200);

    // O critério: o anterior deixa de funcionar imediatamente, sem esperar
    // expiração nenhuma.
    const comAntigo = await request.get(BE10_URL, {
      headers: { Authorization: `Token ${primeiro}` },
    });
    expect(comAntigo.status()).toBe(401);
  });

  test("falha na regeneração vira toast de erro, sem diálogo de token", async ({
    page,
  }) => {
    await stubConfig(page);
    await page.route(REGENERAR_API, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Falha ao gerar o token." }),
      }),
    );
    await abrir(page);

    await page.getByTestId("powerbi-regenerar").click();
    await page.getByTestId("powerbi-regenerar-confirmar").click();

    const toast = page.getByTestId("toast");
    await expect(toast).toBeVisible();
    await expect(toast).toHaveAttribute("data-variant", "error");
    await expect(toast).toContainText("Falha ao gerar o token.");

    // Nada de diálogo de token: não há token novo para exibir.
    await expect(page.getByTestId("powerbi-novo-token")).toHaveCount(0);
    // E o mascarado anterior segue em tela, intocado.
    await expect(page.getByTestId("powerbi-token-mascarado")).toContainText(
      "••••3f2a",
    );
  });
});

// ─── Indicador do snapshot (AC-2) ────────────────────────────────────────────

/**
 * O `status_snapshot` vem calculado do servidor com janela de 1h, e o Beat
 * atualiza o snapshot de hora em hora (`crontab(minute=0)`) — contra o banco
 * real o estado é "em_dia" quase sempre, e ficaria na fronteira do limite
 * justamente perto da virada. Os três estados são exercitados por stub.
 */
test.describe("Power BI — status do snapshot", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  const casos = [
    { status: "em_dia", badge: "Atualizado" },
    { status: "atrasado", badge: "Atrasado" },
    { status: "sem_snapshot", badge: "Sem snapshot" },
  ];

  for (const caso of casos) {
    test(`indica "${caso.badge}" quando o servidor responde ${caso.status}`, async ({
      page,
    }) => {
      await stubConfig(page, {
        status_snapshot: caso.status,
        atualizado_em:
          caso.status === "sem_snapshot"
            ? null
            : new Date(Date.now() - 90 * 60_000).toISOString(),
      });
      await abrir(page);

      const indicador = page.getByTestId("powerbi-snapshot-status");
      await expect(indicador).toHaveAttribute("data-status", caso.status);
      await expect(indicador).toContainText(caso.badge);
    });
  }

  test("o status do servidor prevalece sobre o cálculo local", async ({
    page,
  }) => {
    // Snapshot de 90 minutos atrás: pelo relógio do navegador seria "atrasado".
    // O servidor diz "em_dia" — quem manda é ele, porque é o relógio dele que
    // conta e o do navegador pode estar torto.
    await stubConfig(page, {
      status_snapshot: "em_dia",
      atualizado_em: new Date(Date.now() - 90 * 60_000).toISOString(),
    });
    await abrir(page);

    await expect(page.getByTestId("powerbi-snapshot-status")).toHaveAttribute(
      "data-status",
      "em_dia",
    );
  });

  test("cai no cálculo local quando a resposta não traz o campo", async ({
    page,
  }) => {
    await stubConfig(page, {
      status_snapshot: undefined,
      atualizado_em: new Date(Date.now() - 90 * 60_000).toISOString(),
    });
    await abrir(page);

    await expect(page.getByTestId("powerbi-snapshot-status")).toHaveAttribute(
      "data-status",
      "atrasado",
    );
  });
});

// ─── Ambiente sem token ──────────────────────────────────────────────────────

test.describe("Power BI — nenhum token emitido", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("explica a ausência e oferece emitir o primeiro token", async ({
    page,
  }) => {
    // `token_mascarado: null` é o estado de partida de qualquer instalação —
    // o seed não cria PowerBIToken.
    await stubConfig(page, { token_mascarado: null });
    await abrir(page);

    await expect(page.getByTestId("powerbi-token-mascarado")).toHaveCount(0);
    await expect(page.getByTestId("powerbi-token-ausente")).toContainText(
      "Nenhum token gerado ainda",
    );
    // O rótulo não pode prometer "regenerar" o que não existe.
    await expect(page.getByTestId("powerbi-regenerar")).toContainText(
      "Gerar token",
    );

    await page.getByTestId("powerbi-regenerar").click();
    await expect(
      page.getByText("Ao confirmar, o primeiro token de serviço será emitido."),
    ).toBeVisible();
  });
});

// ─── Gate de Super Admin ─────────────────────────────────────────────────────

test.describe("Power BI — perfil sem permissão", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("o item de menu não aparece para quem não é Super Admin", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Integrações" })).toHaveCount(0);
  });

  test("usuário não Super Admin não acessa a rota direta", async ({ page }) => {
    await page.goto(PAGE_URL);

    // A tela não monta: o gate troca o conteúdo pelo <RestrictedAccess/> 403,
    // padrão das demais telas de /admin — divergência deliberada do texto
    // "redirecionado" no critério da issue (mesma escolha de acessos-sca).
    await expect(page.getByTestId("power-bi-page")).toHaveCount(0);
    // Escopado no <main>: o route announcer do Next também expõe role="alert".
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Erro 403",
    );
    await expect(
      page.getByRole("heading", { name: "Conteúdo restrito" }),
    ).toBeVisible();

    // Nenhuma afordância de regeneração escapa junto com a mensagem.
    await expect(page.getByTestId("powerbi-regenerar")).toHaveCount(0);
  });
});

// ─── Teste de componente: mascaramento ───────────────────────────────────────

/**
 * "Token exibido é mascarado por padrão, sem opção de copiar o valor completo
 * diretamente do DOM sem a ação explícita de regeneração" é o critério de
 * teste de COMPONENTE da issue. Vale a mesma justificativa de
 * google-calendar.spec.ts: o projeto não tem runner de componente, o
 * precedente da casa (semaforo.spec.ts) roda a asserção sobre uma página real,
 * e o que está sob teste aqui é a AUSÊNCIA de uma afordância — afirmação que
 * só se sustenta sobre a árvore inteira que o usuário recebe.
 *
 * A resposta é fixada com um mascarado conhecido para o teste não depender do
 * que houver no banco no momento.
 */
test.describe("Power BI — mascaramento do token", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("token aparece mascarado e sem afordância de copiar o valor completo", async ({
    page,
  }) => {
    await stubConfig(page);
    await abrir(page);

    const card = page.getByTestId("powerbi-token-card");
    const exibido = (await page.getByTestId("powerbi-token-mascarado").innerText()).trim();

    // Mascarado por padrão: pontos e, no máximo, os últimos caracteres.
    expect(exibido).toMatch(/^•+/);
    expect(exibido.replace(/•/g, "").length).toBe(4);

    // Nenhum botão de copiar dentro do card do token — o único "Copiar" da
    // tela é o da URL do endpoint, que não é segredo.
    await expect(card.getByRole("button", { name: "Copiar" })).toHaveCount(0);
    await expect(page.getByTestId("powerbi-copiar-url")).toBeVisible();

    // O diálogo de token em claro e o botão de copiá-lo só existem DEPOIS da
    // ação explícita de regeneração.
    await expect(page.getByTestId("powerbi-novo-token")).toHaveCount(0);
    await expect(page.getByTestId("powerbi-novo-token-copiar")).toHaveCount(0);

    // E nada com cara de segredo escapou para a tela: um token do backend tem
    // 40+ caracteres url-safe seguidos, coisa que o mascarado nunca tem.
    // Sobre o texto renderizado, e não sobre o HTML — lá as cadeias de classe
    // do Tailwind casariam com o padrão por acidente.
    const texto = await page.locator("main").innerText();
    expect(texto).not.toMatch(/[A-Za-z0-9_-]{40,}/);
  });
});
