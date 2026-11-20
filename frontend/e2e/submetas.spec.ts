import { expect, test } from "@playwright/test";
import { criarMetaSemSubmetas, removerMetaSemSubmetas, type MetaSemSubmetas } from "./helpers/submetaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #431 — Cadastro de Submetas no detalhe da Meta, contra o backend real.
 *
 * A Ação exige uma Submeta, e a tela não tinha onde cadastrá-la: uma Meta nova
 * não recebia a primeira Ação. O fluxo pedido na issue: Meta sem Submetas →
 * Nova submeta pela tela → Nova ação ligada a ela, sem recarregar a página.
 */

let meta: MetaSemSubmetas;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  meta = criarMetaSemSubmetas();
});

test.afterAll(() => {
  removerMetaSemSubmetas();
});

test.describe("UGP — Meta → Submeta → Ação", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("Meta sem Submetas: cadastra a Submeta pela tela e em seguida a Ação ligada a ela", async ({ page }) => {
    await page.goto(`/sgp/metas/${meta.id}`);
    await expect(page.getByTestId("meta-detalhe-page")).toBeVisible();

    // Sem Submeta, a tela explica a dependência e não oferece uma Ação que não teria como ser salva.
    const vazio = page.getByTestId("submetas-vazio");
    await expect(vazio).toContainText("Nenhuma Submeta cadastrada");
    await expect(vazio).toContainText("Cadastre a primeira Submeta para poder cadastrar Ações.");

    // A Nova ação, aberta mesmo assim, avisa e leva ao cadastro da Submeta.
    await page.getByTestId("acao-nova-btn").click();
    await expect(page.getByTestId("acao-form-sem-submeta")).toBeVisible();
    await page.getByTestId("acao-form-nova-submeta").click();

    const form = page.getByTestId("submeta-form");
    await expect(form).toBeVisible();
    // Sugere o primeiro número da Meta e começa com o período dela.
    await expect(page.getByTestId("submeta-form-numero")).toHaveValue(`${meta.numero}.1`);
    await expect(page.getByTestId("submeta-form-data-inicio")).toHaveValue(meta.inicio);
    await expect(page.getByTestId("submeta-form-data-fim")).toHaveValue(meta.fim);

    // Período fora do da Meta: a regra do backend, antecipada na tela.
    await page.getByTestId("submeta-form-titulo").fill("Formação de agentes (E2E-431)");
    await page.getByTestId("submeta-form-data-fim").fill("2028-06-30");
    let enviou = false;
    page.on("request", (r) => {
      if (r.url().includes("/api/v1/sgp/submetas/") && r.method() === "POST") enviou = true;
    });
    await page.getByTestId("submeta-form-submit").click();
    await expect(form).toContainText("O período da Submeta deve estar contido no período da Meta");
    expect(enviou).toBe(false);

    await page.getByTestId("submeta-form-data-fim").fill(meta.fim);
    const criada = page.waitForResponse(
      (r) => r.url().includes("/api/v1/sgp/submetas/") && r.request().method() === "POST",
    );
    await page.getByTestId("submeta-form-submit").click();
    const resposta = await criada;
    expect(resposta.status()).toBe(201);
    const submeta = (await resposta.json()) as { id: number; numero: string };
    expect(submeta.numero).toBe(`${meta.numero}.1`);

    // Aparece na lista, sem recarregar.
    const linha = page.getByTestId(`submeta-${submeta.id}`);
    await expect(linha).toContainText("Formação de agentes (E2E-431)");
    await expect(page.getByTestId(`submeta-${submeta.id}-acoes`)).toHaveText("0 ações");
    await expect(page.getByTestId("submetas-vazio")).toHaveCount(0);

    // E no seletor da Nova ação.
    await page.getByTestId("acao-nova-btn").click();
    await expect(page.getByTestId("acao-form")).toBeVisible();
    await expect(page.getByTestId("acao-form-sem-submeta")).toHaveCount(0);
    await page.getByTestId("acao-form-numero").fill(`${meta.numero}.1.1`);
    await page.getByTestId("acao-form-descricao").fill("Oficina de formação (E2E-431).");
    const campoSubmeta = page.getByTestId("acao-form-submeta");
    await campoSubmeta.locator('button[role="combobox"]').click();
    await campoSubmeta.getByRole("option", { name: new RegExp(`^${meta.numero}\\.1 — Formação de agentes`) }).click();
    const indicador = page.getByTestId("acao-form-indicador");
    await indicador.locator('button[role="combobox"]').click();
    await indicador.locator('li[role="option"]').first().click();
    await page.getByTestId("acao-form-quantidade").fill("2");
    await page.getByTestId("acao-form-valor-unitario").fill("150000");
    await page.getByTestId("acao-form-data-inicio").fill("2026-03-01");
    await page.getByTestId("acao-form-data-fim").fill("2026-12-31");

    const acao = page.waitForResponse((r) => r.url().includes("/api/v1/acoes/") && r.request().method() === "POST");
    await page.getByTestId("acao-form-submit").click();
    const respostaAcao = await acao;
    expect(respostaAcao.status()).toBe(201);
    expect(await respostaAcao.json()).toMatchObject({ submeta: submeta.id, numero: `${meta.numero}.1.1` });

    // A Ação entra na tabela, e a Submeta passa a contar 1 ação.
    await expect(page.getByTestId("acoes-table")).toContainText("Oficina de formação (E2E-431).");
    await expect(page.getByTestId(`submeta-${submeta.id}-acoes`)).toHaveText("1 ação");
  });
});

test.describe("Perfil sem gestão do Plano de Trabalho", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  // A Meta do teste fica fora do alcance deste perfil; a Meta 1 do seed, com
  // Submetas, é a mesma que a `acoes.spec.ts` usa para a leitura.
  test("vê as Submetas da Meta, mas não os botões de cadastro", async ({ page }) => {
    await page.goto("/sgp/metas");
    await page.getByTestId("metas-table").getByRole("link", { name: "Visualizar Meta 1" }).click();
    await page.waitForURL(/\/sgp\/metas\/\d+$/);

    await expect(page.getByTestId("submetas-lista")).toBeVisible();
    await expect(page.getByTestId("submetas-lista").locator('[data-testid^="submeta-"][data-testid$="-acoes"]').first()).toHaveText(
      /^\d+ aç(ão|ões)$/,
    );
    await expect(page.getByTestId("submeta-nova-btn")).toHaveCount(0);
    await expect(page.getByTestId("acao-nova-btn")).toHaveCount(0);
  });
});
