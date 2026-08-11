import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Meta usada pelos testes. A 1 é a primeira do seed e tem Ações com Atividades
 * concluídas vinculadas — necessário para o teste de progresso.
 */
const META_NUMERO = 1;

/**
 * Número livre para as Ações criadas pelos testes.
 *
 * Diferente das Metas (numero 1–7, único global, todos ocupados pelo seed), o
 * número da Ação é texto X.Y único apenas dentro da Meta — "9.9" nunca colide
 * com o seed. Por isso estes testes não precisam de fixture de banco.
 */
const NUMERO_LIVRE = "9.9";

function tabelaMetas(page: Page): Locator {
  return page.getByTestId("metas-table").locator("table");
}

function tabelaAcoes(page: Page): Locator {
  return page.getByTestId("acoes-table").locator("table");
}

/** Abre a ficha da Meta pelo botão "visualizar" da listagem. */
async function abrirMeta(page: Page): Promise<void> {
  await page.goto("/sgp/metas");
  await expect(
    tabelaMetas(page).getByRole("cell", { name: "1", exact: true }),
  ).toBeVisible();

  await tabelaMetas(page)
    .getByRole("link", { name: `Visualizar Meta ${META_NUMERO}` })
    .click();

  await page.waitForURL(/\/sgp\/metas\/\d+$/);
  await expect(page.getByTestId("meta-detalhe-page")).toBeVisible();
  await expect(tabelaAcoes(page)).toBeVisible();
}

/** Abre o formulário de nova Ação. Dentro do SlideOver, seletores por testid. */
async function abrirFormularioNovaAcao(page: Page): Promise<Locator> {
  await page.getByTestId("acao-nova-btn").click();
  const form = page.getByTestId("acao-form");
  await expect(form).toBeVisible();
  return form;
}

test.describe("Ações do Plano de Trabalho — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("criar Ação com quantidade e valor unitário exibe o valor total calculado antes de salvar", async ({
    page,
  }) => {
    await abrirMeta(page);
    await abrirFormularioNovaAcao(page);

    const total = page.getByTestId("acao-form-valor-total");
    await expect(total).toContainText("R$ 0,00");

    // 12 × R$ 3.500,00 = R$ 42.000,00 — sem submit, sem tocar o backend.
    await page.getByTestId("acao-form-quantidade").fill("12");
    await page.getByTestId("acao-form-valor-unitario").fill("350000");

    await expect(total).toContainText("R$ 42.000,00");

    // Recalcula ao vivo quando a quantidade muda.
    await page.getByTestId("acao-form-quantidade").fill("3");
    await expect(total).toContainText("R$ 10.500,00");
  });

  test('número em formato inválido ("11") bloqueia o submit com mensagem de erro', async ({
    page,
  }) => {
    await abrirMeta(page);
    await abrirFormularioNovaAcao(page);

    // Falha a criação se alguma requisição escapar da validação de cliente.
    let postou = false;
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/v1/acoes/")) {
        postou = true;
      }
    });

    // Preenche o resto corretamente, para que o único erro possível seja o do
    // número — assim a asserção não passa por acidente.
    await page.getByTestId("acao-form-numero").fill("11");
    await page
      .getByTestId("acao-form-descricao")
      .fill("Ação com número em formato inválido.");
    const tipo = page.getByTestId("acao-form-tipo-unidade");
    await tipo.locator('button[role="combobox"]').click();
    await tipo
      .locator('li[role="option"]')
      .filter({ hasText: /^Oficina$/ })
      .click();

    await page.getByTestId("acao-form-submit").click();

    await expect(page.getByTestId("acao-form")).toContainText(
      "Formato inválido. Use X.Y (ex: 1.1, 2.3).",
    );
    // O painel continua aberto — nada foi salvo.
    await expect(page.getByTestId("acao-form")).toBeVisible();
    expect(postou).toBe(false);

    // E o formato certo limpa o erro.
    await page.getByTestId("acao-form-numero").fill(NUMERO_LIVRE);
    await expect(page.getByTestId("acao-form")).not.toContainText(
      "Formato inválido. Use X.Y",
    );
  });
});

test.describe("Ações do Plano de Trabalho — leitura", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("Ação com Atividades concluídas vinculadas exibe barra de progresso correspondente ao percentual realizado", async ({
    page,
  }) => {
    await abrirMeta(page);

    // Procura uma Ação com progresso > 0 na Meta aberta, em vez de fixar um
    // número: o seed pode mudar, a regra ("realizadas / planejadas") não.
    const linhas = tabelaAcoes(page).getByRole("row");
    const total = await linhas.count();

    let verificadas = 0;
    for (let i = 1; i < total; i++) {
      const linha = linhas.nth(i);
      const barra = linha.getByRole("progressbar");
      const rotulo = (await barra.getAttribute("aria-valuetext")) ?? "";

      // "2 de 12 — Intercâmbio"
      const m = /^(\d+(?:[.,]\d+)?) de (\d+(?:[.,]\d+)?)/.exec(rotulo);
      expect(m, `aria-valuetext inesperado: "${rotulo}"`).not.toBeNull();

      const realizada = Number(m![1].replace(",", "."));
      const planejada = Number(m![2].replace(",", "."));
      const esperado = Math.round((realizada / planejada) * 100);

      await expect(barra).toHaveAttribute("aria-valuenow", String(esperado));
      await expect(barra).toHaveAttribute("aria-valuemax", "100");
      verificadas++;
    }

    expect(verificadas).toBeGreaterThan(0);

    // A Meta 1 do seed tem uma Ação com Atividades concluídas, então pelo menos
    // uma barra precisa estar acima de zero — caso contrário o teste passaria
    // trivialmente com tudo zerado.
    const valores = await tabelaAcoes(page)
      .getByRole("progressbar")
      .evaluateAll((els) =>
        els.map((el) => Number(el.getAttribute("aria-valuenow"))),
      );
    expect(Math.max(...valores)).toBeGreaterThan(0);
  });

  test("perfil sem permissão não vê os botões de criar/editar/excluir Ação", async ({
    page,
  }) => {
    await abrirMeta(page);

    await expect(page.getByTestId("acao-nova-btn")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /^Editar Ação / }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /^Excluir Ação / }),
    ).toHaveCount(0);
  });
});
