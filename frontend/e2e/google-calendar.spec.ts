import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Configurações → Integrações → Google Calendar (tela /admin/integracoes/google-calendar).
 *
 * A tela só monta para o perfil de slug "super-admin" — o mesmo gate de
 * /admin/usuarios e /admin/acessos-sca. Os testes de escrita usam o
 * `superAdmin` do `manage.py seed_demo` (vera.lucena@demo.pdhc.local).
 *
 * A configuração é um SINGLETON do banco compartilhado pela suíte: não há
 * registro descartável para mexer, como acontece nas telas de listagem. Por
 * isso todo teste que grava captura o estado inicial, faz a ida e a volta, e
 * ainda restaura no `finally` — uma falha no meio não pode deixar a integração
 * ligada para as execuções seguintes.
 */
const PAGE_URL = "/admin/integracoes/google-calendar";

/** Só o status agregado (BE-4) — a config em si continua vindo do backend. */
const STATUS_API = /\/api\/v1\/core\/config\/google-calendar\/status\/$/;

/** Lembrete usado nas edições. Não está no seed, que semeia [1440, 60]. */
const LEMBRETE_NOVO = 45;

const CALENDARIO_TESTE = "agenda-e2e@group.calendar.google.com";

// ─── Locators ────────────────────────────────────────────────────────────────

const calendarioId = (page: Page): Locator =>
  page.getByTestId("gcal-calendario-destino-id");
const chips = (page: Page): Locator => page.getByTestId("gcal-lembretes-chip");
const chip = (page: Page, minutos: number): Locator =>
  page.locator(`[data-testid="gcal-lembretes-chip"][data-minutos="${minutos}"]`);
const toggle = (page: Page): Locator => page.getByTestId("gcal-integracao-ativa");
const salvar = (page: Page): Locator => page.getByTestId("gcal-salvar");

/**
 * Abre a tela e espera os dados chegarem.
 *
 * O card de status só é renderizado depois de o GET da configuração resolver
 * NO NAVEGADOR, então esperá-lo serve de duas coisas ao mesmo tempo: garante
 * que há dado na tela e que o React já hidratou — sem isso o clique no toggle
 * chegaria antes do handler existir e se perderia em silêncio.
 */
async function abrir(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("google-calendar-page")).toBeVisible();
  await expect(page.getByTestId("gcal-status")).toBeVisible();
}

type Configuracao = {
  calendario: string;
  lembretes: number[];
  ativa: boolean;
};

/** Lê da tela o que está persistido no momento. */
async function lerConfiguracao(page: Page): Promise<Configuracao> {
  const minutos = await chips(page).evaluateAll((els) =>
    els.map((el) => Number(el.getAttribute("data-minutos"))),
  );
  return {
    calendario: await calendarioId(page).inputValue(),
    lembretes: minutos,
    ativa: (await toggle(page).getAttribute("aria-checked")) === "true",
  };
}

async function adicionarLembrete(page: Page, minutos: number): Promise<void> {
  await page.getByTestId("gcal-lembretes-input").fill(String(minutos));
  await page.getByTestId("gcal-lembretes-adicionar").click();
  await expect(chip(page, minutos)).toBeVisible();
}

async function salvarEsperandoToast(page: Page): Promise<void> {
  await salvar(page).click();
  const toast = page.getByTestId("toast");
  await expect(toast).toBeVisible();
  await expect(toast).toHaveAttribute("data-variant", "success");
  await expect(toast).toContainText("Configurações salvas.");
}

/**
 * Devolve a tela ao estado informado. Idempotente: se já estiver lá, o botão
 * Salvar continua desabilitado e a função sai sem gravar nada.
 */
async function restaurar(page: Page, alvo: Configuracao): Promise<void> {
  await abrir(page);

  await calendarioId(page).fill(alvo.calendario);

  for (const el of await chips(page).all()) {
    const minutos = Number(await el.getAttribute("data-minutos"));
    if (!alvo.lembretes.includes(minutos)) {
      await el.getByRole("button").click();
    }
  }
  for (const minutos of alvo.lembretes) {
    if ((await chip(page, minutos).count()) === 0) {
      await adicionarLembrete(page, minutos);
    }
  }

  if (((await toggle(page).getAttribute("aria-checked")) === "true") !== alvo.ativa) {
    await toggle(page).click();
  }

  if (await salvar(page).isEnabled()) {
    await salvarEsperandoToast(page);
  }
}

// ─── Persistência ────────────────────────────────────────────────────────────

test.describe("Google Calendar — Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("lembretes e toggle persistem depois de recarregar a página", async ({
    page,
  }) => {
    await abrir(page);
    const inicial = await lerConfiguracao(page);

    // Um LEMBRETE_NOVO já presente aqui é resíduo de uma execução anterior que
    // morreu antes do `finally` — o teste não teria o que provar ao adicioná-lo.
    expect(inicial.lembretes).not.toContain(LEMBRETE_NOVO);

    try {
      await calendarioId(page).fill(CALENDARIO_TESTE);
      await adicionarLembrete(page, LEMBRETE_NOVO);
      await toggle(page).click();
      const ativaEditada = !inicial.ativa;
      await expect(toggle(page)).toHaveAttribute(
        "aria-checked",
        String(ativaEditada),
      );

      await expect(page.getByTestId("gcal-alteracoes-nao-salvas")).toBeVisible();
      await salvarEsperandoToast(page);
      // Salvo é salvo: o aviso some porque o formulário deixou de estar sujo.
      await expect(page.getByTestId("gcal-alteracoes-nao-salvas")).toHaveCount(0);

      await abrir(page);
      const depois = await lerConfiguracao(page);
      expect(depois.calendario).toBe(CALENDARIO_TESTE);
      expect(depois.lembretes).toContain(LEMBRETE_NOVO);
      expect(depois.ativa).toBe(ativaEditada);

      // Volta ao estado inicial pela própria tela: é o "reativar" do critério
      // (o toggle tem de persistir nos dois sentidos, não só ao desligar).
      await chip(page, LEMBRETE_NOVO).getByRole("button").click();
      await toggle(page).click();
      await calendarioId(page).fill(inicial.calendario);
      await salvarEsperandoToast(page);

      await abrir(page);
      expect(await lerConfiguracao(page)).toEqual(inicial);
    } finally {
      await restaurar(page, inicial);
    }
  });
});

// ─── Indicador de status (BE-4) ──────────────────────────────────────────────

/**
 * O `seed_demo` não cria nenhum `GoogleCalendarSyncEvent`, então contra o banco
 * real o card só sabe dizer "nunca sincronizado". Os cenários com data e com
 * falha são montados interceptando `.../status/` — o mesmo recurso usado em
 * membros.spec.ts e formularios.spec.ts. A configuração continua vindo do
 * backend de verdade: só o status é fixado.
 */
async function stubStatus(
  page: Page,
  corpo: Record<string, unknown>,
): Promise<void> {
  await page.route(STATUS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(corpo),
    });
  });
}

const minutosAtras = (minutos: number): string =>
  new Date(Date.now() - minutos * 60_000).toISOString();

test.describe("Google Calendar — status da sincronização", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("mostra há quanto tempo foi a última sincronização", async ({ page }) => {
    await stubStatus(page, {
      estado: "ok",
      ultima_sincronizacao: minutosAtras(3),
      ultimo_erro: null,
      falhas_recentes: 0,
    });
    await abrir(page);

    const status = page.getByTestId("gcal-status");
    await expect(status).toHaveAttribute("data-estado", "ok");
    await expect(status).toContainText("Sincronizado");
    await expect(page.getByTestId("gcal-ultima-sincronizacao")).toContainText(
      "há 3 minutos",
    );
    await expect(page.getByTestId("gcal-falhas-recentes")).toHaveCount(0);
    await expect(page.getByTestId("gcal-ultimo-erro")).toHaveCount(0);
  });

  test("sinaliza falha recente com badge e mensagem de erro", async ({ page }) => {
    await stubStatus(page, {
      estado: "erro",
      ultima_sincronizacao: minutosAtras(180),
      ultimo_erro: "403: calendarUsageLimitsExceeded",
      falhas_recentes: 2,
    });
    await abrir(page);

    const status = page.getByTestId("gcal-status");
    await expect(status).toHaveAttribute("data-estado", "erro");
    await expect(status).toContainText("Falha na sincronização");
    await expect(page.getByTestId("gcal-falhas-recentes")).toContainText(
      "2 falha(s) registrada(s) nas últimas 24 horas",
    );
    await expect(page.getByTestId("gcal-ultimo-erro")).toContainText(
      "403: calendarUsageLimitsExceeded",
    );
  });

  test("avisa das falhas das últimas 24h mesmo com a sincronização recuperada", async ({
    page,
  }) => {
    // `falhas_recentes` é janela rolando de 24h e não zera depois de um sucesso;
    // `ultimo_erro` é histórico. Sem o badge extra, um "Sincronizado" verde
    // esconderia que a integração falhou duas vezes hoje.
    await stubStatus(page, {
      estado: "ok",
      ultima_sincronizacao: minutosAtras(5),
      ultimo_erro: "429: rateLimitExceeded",
      falhas_recentes: 2,
    });
    await abrir(page);

    const status = page.getByTestId("gcal-status");
    await expect(status).toHaveAttribute("data-estado", "ok");
    await expect(status).toContainText("2 falha(s) em 24h");
    // O erro fica rotulado como histórico — não é o estado atual.
    await expect(page.getByTestId("gcal-ultimo-erro")).toContainText(
      "Último erro registrado: 429: rateLimitExceeded",
    );
  });
});

// ─── Gate de Super Admin ─────────────────────────────────────────────────────

test.describe("Google Calendar — perfil sem permissão", () => {
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
    await expect(page.getByTestId("google-calendar-page")).toHaveCount(0);
    // Escopado no <main>: o route announcer do Next também expõe role="alert".
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Erro 403",
    );
    await expect(
      page.getByRole("heading", { name: "Conteúdo restrito" }),
    ).toBeVisible();

    // E nenhuma afordância de edição escapa junto com a mensagem.
    await expect(page.getByTestId("gcal-salvar")).toHaveCount(0);
  });
});

// ─── Teste de componente: credenciais ────────────────────────────────────────

/**
 * "Nenhum campo de credencial sensível é renderizado no DOM" é o critério de
 * teste de COMPONENTE da issue. O projeto não tem runner de componente (só
 * Playwright), e o precedente da casa para esse caso é semaforo.spec.ts, que
 * roda a asserção de componente sobre uma página real.
 *
 * Aqui a página tem de ser a própria tela, e não o /styleguide: o que está sob
 * teste é justamente a AUSÊNCIA de um campo, e essa afirmação só vale sobre a
 * árvore completa que o usuário recebe, com a configuração já carregada. Um
 * styleguide provaria apenas que o bloco escolhido não tem credencial.
 *
 * A varredura olha id, name, placeholder, rótulo e aria-label de todo controle
 * de formulário, e depois o HTML inteiro do <main> — assim um campo novo
 * chamado "client_secret" reprova mesmo que ninguém lembre de atualizar o teste.
 */
const PADRAO_SENSIVEL =
  /client[ _-]?id|client[ _-]?secret|secret|senha|password|token|credential|credencial|private[ _-]?key|refresh[ _-]?token|api[ _-]?key/i;

test.describe("Google Calendar — credenciais", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("nenhum campo de credencial é renderizado no DOM", async ({ page }) => {
    await abrir(page);

    const campos = await page
      .locator("main input, main textarea, main select")
      .evaluateAll((els) =>
        els.map((el) => {
          const input = el as HTMLInputElement;
          const rotulo = input.labels
            ? Array.from(input.labels)
                .map((l) => l.textContent ?? "")
                .join(" ")
            : "";
          return {
            type: input.type ?? "",
            descricao: [
              input.id,
              input.name ?? "",
              input.placeholder ?? "",
              input.getAttribute("aria-label") ?? "",
              rotulo,
            ].join(" "),
          };
        }),
      );

    // Guarda: sem esta linha o teste passaria com a tela vazia, provando nada.
    expect(campos.length).toBeGreaterThan(0);

    for (const campo of campos) {
      expect(campo.descricao).not.toMatch(PADRAO_SENSIVEL);
      expect(campo.type).not.toBe("password");
    }

    // O HTML inteiro: pega também valor renderizado fora de <input>, como um
    // trecho de service account impresso em <pre> ou <code>.
    const html = await page.locator("main").innerHTML();
    expect(html).not.toMatch(
      /client[_-]?secret|private[_-]?key|refresh[_-]?token/i,
    );

    // O que a tela mostra no lugar: só a indicação textual da issue.
    const credenciais = page.getByTestId("gcal-credenciais");
    await expect(credenciais).toContainText("Credenciais OAuth2");
    await expect(credenciais).toContainText(/variável de ambiente/i);
    await expect(credenciais).toContainText(/não são exibidas nem editáveis/i);
    await expect(
      credenciais.locator("input, textarea, select, button"),
    ).toHaveCount(0);
  });
});
