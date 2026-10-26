import { expect, test, type Page } from "@playwright/test";
import {
  criarTipoRubricaFixture,
  removerTipoRubricaFixture,
  type TipoRubricaFixture,
} from "./helpers/tipoRubricaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #319 (SGD-FE-8) — Configurações → SGD → Tipos e Rubricas, contra o CRUD
 * real da BE-8.
 *
 * Só a lista de rubricas é simulada: `GET /api/v1/sgp/rubricas/` ainda não
 * existe no backend (pendencias-backend-sprint-11.md, item 1). A resposta
 * usa os ids reais, lidos pela fixture.
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

async function simularRubricas(page: Page) {
  await page.route(
    (url) => url.pathname === "/api/v1/sgp/rubricas/",
    (route) => {
      if (route.request().method() === "OPTIONS") return route.fallback();
      return route.fulfill({
        status: 200,
        headers: { "access-control-allow-origin": "*", "content-type": "application/json" },
        body: JSON.stringify(fx.rubricas),
      });
    },
  );
}

/** Abre um `Select` do design system pelo id do campo e escolhe a opção. */
async function escolher(page: Page, id: string, opcao: string) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao, exact: true }).click();
}

const mapeamentoDoTipo = (tipo: string) => fx.mapeamentos.find((m) => m.tipo === tipo && m.ativo)!;
const rubrica = (slug: string) => fx.rubricas.find((r) => r.slug === slug)!;

test.describe("Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test.beforeEach(async ({ page }) => {
    await simularRubricas(page);
  });

  test("chega pela área de Configurações e vê um mapeamento ativo por tipo", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Configurações" }).click();
    await expect(page).toHaveURL(/\/admin\/configuracoes\/?$/);
    await page.getByTestId("configuracao-card-tipos-rubricas").click();
    await expect(page).toHaveURL(new RegExp(`${TELA}/?$`));

    const tabela = page.getByTestId("mapeamentos-tabela");
    for (const m of fx.mapeamentos.filter((x) => x.ativo)) {
      await expect(tabela.getByTestId(`mapeamento-${m.id}`)).toContainText("Ativo");
    }
    const veiculo = tabela.getByTestId(`mapeamento-${mapeamentoDoTipo("veiculo").id}`);
    await expect(veiculo).toContainText("Locação de Veículo");
  });

  test("desativa, cria um novo para o tipo, edita a rubrica e desativa de novo", async ({ page }) => {
    const antigo = mapeamentoDoTipo("veiculo");
    await page.goto(TELA);

    // Desativar: o tipo fica livre para um novo mapeamento.
    await page.getByTestId(`mapeamento-situacao-${antigo.id}`).click();
    await expect(page.getByTestId("situacao-drawer")).toContainText(AVISO);
    await page.getByTestId("situacao-confirmar").click();
    await expect(page.getByText(`Mapeamento desativado. A alteração ${AVISO}`)).toBeVisible();
    // Sem "Mostrar inativos", o desativado sai da lista.
    await expect(page.getByTestId(`mapeamento-${antigo.id}`)).toHaveCount(0);

    // Criar.
    await page.getByTestId("mapeamento-novo").click();
    const form = page.getByTestId("mapeamento-form");
    await expect(form).toContainText(AVISO);
    await escolher(page, "mapeamento-tipo", "Locação de Veículo");
    await escolher(page, "mapeamento-rubrica", rubrica("locacao-veiculo").nome);
    const criacao = page.waitForResponse(
      (r) => r.url().includes("/api/v1/sgd/config/tipo-rubrica/") && r.request().method() === "POST",
    );
    await page.getByTestId("mapeamento-salvar").click();
    const criado = await (await criacao).json();
    await expect(page.getByText(`Mapeamento criado. A alteração ${AVISO}`)).toBeVisible();
    const linha = page.getByTestId(`mapeamento-${criado.id}`);
    await expect(linha).toContainText("Locação de Veículo");
    await expect(linha).toContainText("Ativo");

    // Editar a rubrica (o tipo fica fixo na edição).
    await page.getByTestId(`mapeamento-editar-${criado.id}`).click();
    await expect(page.locator("button#mapeamento-tipo")).toBeDisabled();
    await escolher(page, "mapeamento-rubrica", rubrica("material-grafico").nome);
    await page.getByTestId("mapeamento-salvar").click();
    await expect(page.getByText(`Mapeamento atualizado. A alteração ${AVISO}`)).toBeVisible();
    await expect(linha).toContainText(rubrica("material-grafico").nome);

    // Desativar o novo; com "Mostrar inativos", os dois aparecem como Inativo.
    await page.getByTestId(`mapeamento-situacao-${criado.id}`).click();
    await page.getByTestId("situacao-confirmar").click();
    await expect(page.getByText(`Mapeamento desativado. A alteração ${AVISO}`).last()).toBeVisible();
    await page.getByTestId("mapeamentos-incluir-inativos").check();
    await expect(page.getByTestId(`mapeamento-${antigo.id}`)).toContainText("Inativo");
    await expect(page.getByTestId(`mapeamento-${criado.id}`)).toContainText("Inativo");
  });

  test("um segundo mapeamento ativo para o mesmo tipo é barrado antes de chamar a API", async ({
    page,
  }) => {
    const posts: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/v1/sgd/config/tipo-rubrica/")) posts.push(req.url());
    });
    await page.goto(TELA);

    await page.getByTestId("mapeamento-novo").click();
    await escolher(page, "mapeamento-tipo", "Diárias");
    const form = page.getByTestId("mapeamento-form");
    await expect(form).toContainText("Já existe um mapeamento ativo para este tipo de solicitação.");
    await escolher(page, "mapeamento-rubrica", rubrica("diarias").nome);
    await page.getByTestId("mapeamento-salvar").click();

    // Continua aberto, com o aviso, e nenhum POST saiu.
    await expect(form).toBeVisible();
    await expect(form).toContainText("Já existe um mapeamento ativo para este tipo de solicitação.");
    expect(posts).toEqual([]);

    // Desmarcar "Ativo" libera: um inativo pode coexistir com o ativo.
    await page.getByTestId("mapeamento-ativo").uncheck();
    await expect(form).not.toContainText("Já existe um mapeamento ativo");
  });

  test("reativar um inativo com outro ativo no tipo é barrado com aviso", async ({ page }) => {
    const antigo = mapeamentoDoTipo("diaria");
    await page.goto(TELA);
    await page.getByTestId("mapeamento-novo").click();
    await escolher(page, "mapeamento-tipo", "Diárias");
    await escolher(page, "mapeamento-rubrica", rubrica("passagens-aereas").nome);
    await page.getByTestId("mapeamento-ativo").uncheck();
    const criacao = page.waitForResponse(
      (r) => r.url().includes("/api/v1/sgd/config/tipo-rubrica/") && r.request().method() === "POST",
    );
    await page.getByTestId("mapeamento-salvar").click();
    const inativo = await (await criacao).json();

    await page.getByTestId("mapeamentos-incluir-inativos").check();
    await page.getByTestId(`mapeamento-situacao-${inativo.id}`).click();
    await expect(page.getByText("Desative o atual antes de reativar este.")).toBeVisible();
    await expect(page.getByTestId("situacao-drawer")).toHaveCount(0);
    await expect(page.getByTestId(`mapeamento-${antigo.id}`)).toContainText("Ativo");
  });
});

for (const perfil of ["ugp", "adt"] as const) {
  test.describe(`Perfil ${perfil}`, () => {
    test.use({ storageState: storageStatePath(perfil) });

    test("não acessa a tela nem vê Configurações no menu", async ({ page }) => {
      await page.goto(TELA);
      await expect(page.getByText("Conteúdo restrito")).toBeVisible();
      await expect(page.getByTestId("mapeamentos-tabela")).toHaveCount(0);
      await expect(page.getByRole("link", { name: "Configurações" })).toHaveCount(0);
    });
  });
}
