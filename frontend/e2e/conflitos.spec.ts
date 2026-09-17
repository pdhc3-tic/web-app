import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Conflitos de sincronização do SCA (FE-11).
 *
 * ─── Por que a suíte recria as fixtures ─────────────────────────────────────
 *
 * Resolver um conflito é irreversível pela API: não existe caminho que devolva
 * um `ConflictLog` a `pendente`. O teste de resolução consome o registro que
 * verifica, então sem recriar as fixtures a segunda execução não teria o que
 * resolver e falharia por falta de dado, não por defeito.
 *
 * `seed_demo --sca-only` reconstrói apenas dispositivos, eventos e conflitos —
 * as UPFs, as Metas e as Atividades do restante da suíte ficam intactas.
 *
 * ─── O par de articuladores ─────────────────────────────────────────────────
 *
 * O seed vincula Sandra a PE/AL/MA e Hélio a PB/RN/BA/MG, e cria um pendente
 * sensível de cada lado. Território nulo no perfil significaria acesso global
 * (ver o help_text de `UserProfile.territorio`), e o recorte não seria
 * observável.
 */

/** Campos dos dois conflitos sensíveis semeados, um em cada estado. */
const CAMPO_PE = "CPF do titular";
const CAMPO_PB = "Nome do titular";

function recriarFixturesSca(): void {
  execFileSync(
    "docker",
    ["exec", "backend", "python", "manage.py", "seed_demo", "--sca-only"],
    { stdio: "pipe", timeout: 120_000 },
  );
}

async function abrirLista(page: Page): Promise<void> {
  await page.goto("/sca/conflitos");
  await expect(page.getByTestId("conflitos-page")).toBeVisible();
  // A tabela só existe com dados carregados — esperar por ela evita ler a lista
  // no instante em que ainda está vazia.
  await expect(page.getByTestId("conflitos-table")).toBeVisible();
}

/** Linha do conflito cujo campo é o informado (vazia quando não há). */
function linhaDoCampo(page: Page, campo: string) {
  return page
    .locator('[data-testid^="conflito-row-"]')
    .filter({ hasText: campo });
}

test.describe("Conflitos de sincronização — Articulador de PE", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  // Por teste, e não por bloco: a resolução consome o conflito pendente, e o
  // teste do sino abre ESSE conflito esperando encontrá-lo em aberto. Semear
  // uma vez só por bloco deixa a ordem de declaração decidir o resultado.
  test.beforeEach(() => {
    recriarFixturesSca();
  });

  test("conflito em CPF aparece destacado como sensível e sem resolução automática", async ({
    page,
  }) => {
    await abrirLista(page);

    const linha = linhaDoCampo(page, CAMPO_PE);
    await expect(linha).toHaveCount(1);
    await expect(linha).toHaveAttribute("data-sensivel", "true");
    await expect(linha.getByTestId("conflito-sensivel")).toBeVisible();
    await expect(linha.getByTestId("conflito-status")).toHaveAttribute(
      "data-status",
      "pendente",
    );

    await linha.getByRole("link").first().click();
    await expect(page.getByTestId("conflito-detalhe-page")).toBeVisible();

    // O aviso de revisão obrigatória é o que diferencia o campo sensível.
    await expect(page.getByTestId("conflito-aviso-sensivel")).toContainText(
      "revisão manual é obrigatória",
    );

    // A UI não pode oferecer NENHUM caminho de auto-resolução: as três opções
    // são escolhas de valor, e não há botão que dispense a decisão.
    await expect(page.getByTestId("conflito-opcao-servidor")).toBeVisible();
    await expect(page.getByTestId("conflito-opcao-local")).toBeVisible();
    await expect(page.getByTestId("conflito-opcao-manual")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /autom[áa]tic/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /marcar como resolvido/i }),
    ).toHaveCount(0);
  });

  test("resolver pelo valor do servidor aplica a decisão e tira o item dos pendentes", async ({
    page,
  }) => {
    await abrirLista(page);

    const linha = linhaDoCampo(page, CAMPO_PE);
    await expect(linha).toHaveCount(1);
    // O valor do servidor mostrado na lista é o que deve prevalecer no fim.
    const valorServidor = (
      await linha.locator("td").nth(2).innerText()
    ).trim();

    await linha.getByRole("link").first().click();
    await expect(page.getByTestId("conflito-detalhe-page")).toBeVisible();
    const url = page.url();

    await page.getByTestId("conflito-opcao-servidor").click();
    await page.getByTestId("conflito-confirmar").click();

    // Sucesso devolve à lista, e lá o conflito não está mais pendente.
    await page.waitForURL("**/sca/conflitos");
    await expect(page.getByTestId("conflitos-page")).toBeVisible();
    await expect(page.getByTestId("conflitos-table")).toBeVisible();
    await expect(
      linhaDoCampo(page, CAMPO_PE).getByTestId("conflito-status"),
    ).toHaveAttribute("data-status", "resolvido_manual");

    // Filtrar por pendentes confirma que ele saiu da fila de trabalho.
    await page.goto("/sca/conflitos?status=pendente");
    await expect(page.getByTestId("conflitos-page")).toBeVisible();
    await expect(linhaDoCampo(page, CAMPO_PE)).toHaveCount(0);

    // E o registro definitivo guardou o valor escolhido, com autoria.
    await page.goto(url);
    const resolvido = page.getByTestId("conflito-resolvido");
    await expect(resolvido).toBeVisible();
    await expect(resolvido).toContainText(valorServidor);
    await expect(resolvido).toContainText("Sandra Queiroz");
    await expect(page.getByTestId("conflito-resolucao")).toHaveCount(0);
  });

  test("a notificação do sino leva ao conflito que a originou", async ({
    page,
  }) => {
    // A notificação é criada pelo backend (apps/sca/tasks.py) com o link
    // /sca/conflitos/{id} — este teste fecha o circuito entre o aviso e a tela.
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /^Notificações/ }).click();

    const painel = page.getByRole("dialog", { name: "Notificações" });
    const aviso = painel
      .getByRole("link")
      .filter({ hasText: "Conflito de sincronização em campo sensível" });
    await expect(aviso.first()).toBeVisible();
    await aviso.first().click();

    await page.waitForURL(/\/sca\/conflitos\/\d+$/);
    await expect(page.getByTestId("conflito-detalhe-page")).toBeVisible();
    await expect(page.getByTestId("conflito-aviso-sensivel")).toBeVisible();
  });

  test("não enxerga os conflitos de outro estado", async ({ page }) => {
    await abrirLista(page);

    await expect(linhaDoCampo(page, CAMPO_PE)).toHaveCount(1);
    await expect(linhaDoCampo(page, CAMPO_PB)).toHaveCount(0);
  });
});

test.describe("Conflitos de sincronização — Articulador de PB", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  // Aqui basta uma vez: os dois testes deste bloco são de leitura.
  test.beforeAll(() => {
    recriarFixturesSca();
  });

  test("vê o conflito do próprio estado e não o do vizinho", async ({ page }) => {
    await abrirLista(page);

    await expect(linhaDoCampo(page, CAMPO_PB)).toHaveCount(1);
    await expect(linhaDoCampo(page, CAMPO_PE)).toHaveCount(0);
  });

  test("abrir pelo id um conflito de outro estado não revela o dado", async ({
    page,
  }) => {
    // O queryset recorta antes do detalhe: para quem não pode ver, o conflito
    // não existe. Vale testar pelo id porque o link da notificação leva direto
    // ao detalhe, sem passar pela lista.
    await abrirLista(page);
    const testid = await linhaDoCampo(page, CAMPO_PB)
      .first()
      .getAttribute("data-testid");
    const idVisivel = Number(testid?.replace("conflito-row-", ""));
    expect(idVisivel).toBeGreaterThan(0);

    // Os conflitos do seed são criados em sequência; o do outro estado é
    // vizinho imediato deste. Se o id não existir, a tela também não vaza nada.
    for (const candidato of [idVisivel - 1, idVisivel + 1]) {
      await page.goto(`/sca/conflitos/${candidato}`);
      await expect(page.getByTestId("conflito-detalhe-page")).toHaveCount(0);
    }
  });
});

/**
 * A UGP enxerga o restante do SCA, mas não os conflitos: o aceite limita a
 * revisão a Articulador Estadual e Super Admin.
 *
 * O que este bloco cobre é a afordância — menu escondido e rota bloqueada. O
 * recorte de dados é do backend e entrou na PR #213: `get_queryset` devolve
 * `qs.none()` para o perfil `ugp` e `resolver` nega pelo
 * `has_object_permission`. Uma coisa não substitui a outra — este bloco segue
 * provando que a tela não oferece o caminho.
 */
test.describe("Conflitos de sincronização — UGP não revisa conflitos", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("não vê o item de menu de conflitos", async ({ page }) => {
    await page.goto("/dashboard");

    // Âncora: o menu precisa ter renderizado, senão uma sidebar ausente
    // passaria por "item escondido". "SCA" é item de módulo, visível a todos.
    await expect(
      page.getByRole("link", { name: "SCA", exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Conflitos SCA" })).toHaveCount(
      0,
    );
  });

  test("acesso direto à lista e ao detalhe cai no estado de acesso negado", async ({
    page,
  }) => {
    await page.goto("/sca/conflitos");
    await expect(page.getByTestId("conflitos-page")).toHaveCount(0);
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Conteúdo restrito",
    );

    // O gate do detalhe é independente do da lista — vale checar os dois.
    await page.goto("/sca/conflitos/1");
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
  });
});

test.describe("Conflitos de sincronização — perfil sem acesso", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("não vê o item de menu nem a tela ao acessar a rota direto", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(
      page.getByRole("link", { name: "Conflitos SCA" }),
    ).toHaveCount(0);

    await page.goto("/sca/conflitos");
    await expect(page.getByTestId("conflitos-page")).toHaveCount(0);
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
  });
});
