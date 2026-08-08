import { expect, test, type Locator, type Page } from "@playwright/test";
import { SLOT_NUMERO, freeMetaSlot, restoreMetaSlot } from "./helpers/metaSlot";
import { storageStatePath } from "./helpers/users";

const METAS_URL = "/sgp/metas";

/**
 * A tela renderiza duas listagens (tabela em ≥768px, cards abaixo disso).
 * Escopar na tabela evita que um seletor case as duas e caia no strict mode.
 */
function tabela(page: Page): Locator {
  return page.getByTestId("metas-table").locator("table");
}

async function abrirMetas(page: Page): Promise<void> {
  await page.goto(METAS_URL);
  await expect(
    page.getByRole("heading", { name: "Metas do Plano de Trabalho" }),
  ).toBeVisible();
  // Espera o fim do skeleton: a primeira Meta do seed é a de número 1.
  await expect(
    tabela(page).getByRole("cell", { name: "1", exact: true }),
  ).toBeVisible();
}

// ─────────────────────────────────────────────────────────────────────────────
// UGP — pode criar, editar e excluir
// ─────────────────────────────────────────────────────────────────────────────

test.describe("Metas — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.describe("criação", () => {
    // O seed ocupa os 7 números possíveis; libera um antes e devolve depois.
    test.beforeAll(() => freeMetaSlot());
    test.afterAll(() => restoreMetaSlot());

    test('cria uma nova Meta com todos os campos e ela aparece na listagem com status "No prazo"', async ({
      page,
    }) => {
      const titulo = `Meta E2E ${Date.now()}`;

      await abrirMetas(page);
      await page.getByTestId("meta-nova-btn").click();

      const form = page.getByTestId("meta-form");
      await expect(form).toBeVisible();

      // Dentro do SlideOver os seletores são por testid/CSS, não por role: o
      // backdrop que envolve o painel tem aria-hidden="true", então nada do
      // conteúdo aparece na árvore de acessibilidade (ver SlideOver.tsx).
      const numero = page.getByTestId("meta-form-numero");
      await numero.locator('button[role="combobox"]').click();
      await numero
        .locator('li[role="option"]')
        .filter({ hasText: new RegExp(`^Meta ${SLOT_NUMERO}$`) })
        .click();

      await page.getByTestId("meta-form-titulo").fill(titulo);
      await page
        .getByTestId("meta-form-descricao")
        .fill("Meta cadastrada pelo teste E2E do Plano de Trabalho.");

      const ods = page.getByTestId("meta-form-ods");
      for (const rotulo of [
        "ODS 4 – Educação de Qualidade",
        "ODS 13 – Ação contra a Mudança Global do Clima",
      ]) {
        await ods
          .locator("label")
          .filter({ hasText: rotulo })
          .locator('input[type="checkbox"]')
          .check();
      }

      await page.getByTestId("meta-form-data-inicio").fill("2026-03-01");
      await page.getByTestId("meta-form-data-fim").fill("2027-12-31");

      await page.getByTestId("meta-form-submit").click();

      await expect(page.getByTestId("toast")).toContainText(
        "Meta criada com sucesso.",
      );
      await expect(form).toBeHidden();

      const linha = tabela(page).getByRole("row").filter({ hasText: titulo });
      await expect(linha).toBeVisible();
      await expect(linha.getByRole("cell").first()).toHaveText(
        String(SLOT_NUMERO),
      );
      await expect(linha).toContainText("01/03/2026 – 31/12/2027");
      // Meta recém-criada não tem Ações → status_calculado = "no_prazo".
      await expect(linha).toContainText("No prazo");
    });
  });

  test("tentativa de excluir Meta com Ações vinculadas exibe mensagem de erro do backend", async ({
    page,
  }) => {
    await abrirMetas(page);

    const linha = tabela(page)
      .getByRole("row")
      .filter({ has: page.getByRole("button", { name: "Excluir Meta 1" }) });
    await expect(linha).toBeVisible();
    const titulo = (await linha.getByRole("cell").nth(1).innerText()).trim();

    await linha.getByRole("button", { name: "Excluir Meta 1" }).click();
    const confirmar = page.getByTestId("meta-excluir-confirmar");
    await expect(confirmar).toBeVisible();
    await confirmar.click();

    const toast = page.getByTestId("toast");
    await expect(toast).toHaveAttribute("data-variant", "error");
    await expect(toast).toContainText(
      "Não é possível excluir esta Meta: existem Ações vinculadas a ela.",
    );

    // A listagem continua intacta — o backend recusou a exclusão.
    await expect(
      tabela(page).getByRole("row").filter({ hasText: titulo }),
    ).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// ADT/ACR — leitura liberada, escrita bloqueada
// ─────────────────────────────────────────────────────────────────────────────

test.describe("Metas — usuário sem permissão", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("não visualiza os botões de criar/editar/excluir", async ({ page }) => {
    await abrirMetas(page);

    // A tela continua legível: as Metas do seed aparecem normalmente.
    await expect(
      tabela(page).getByRole("row").filter({ hasText: /\S/ }),
    ).not.toHaveCount(0);

    await expect(page.getByTestId("meta-nova-btn")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /^Editar Meta \d+$/ }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /^Excluir Meta \d+$/ }),
    ).toHaveCount(0);
    // Sem a coluna de ações a tabela fica com 5 colunas.
    await expect(tabela(page).locator("thead th")).toHaveCount(5);
  });
});
