import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Tela de configuração do mapeamento Arlo ↔ SGD (#320, SGD-FE-9) em
 * /admin/configuracoes/sgd/integracao-arlo.
 *
 * Rola contra o CRUD real do backend (BE-9) e o `seed_demo` — a migration
 * `sgd.0007_seed_arlo_mapeamento` traz o mapeamento padrão em duas direções
 * (10 colunas na exportação, 6 na importação).
 *
 * Catálogo de campos e preview da linha dependem de rotas que ainda não
 * existem (pendencias-backend-sprint-11.md item 2 / #373). Enquanto não
 * existem, a tela usa o fallback do catálogo e mostra o aviso no lugar do
 * preview — os testes abaixo cobrem exatamente esse cenário atual.
 */

const PAGE_URL = "/admin/configuracoes/sgd/integracao-arlo";
const REORDENAR_API = /\/api\/v1\/sgd\/config\/arlo-mapping\/reordenar\/$/;

async function abrir(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("arlo-mapping-page")).toBeVisible();
  // Mapeamento padrão da migration: espera "demanda_id" aparecer na direção
  // de exportação (que é a aba default).
  await expect(page.getByTestId("arlo-linha-demanda_id")).toBeVisible();
}

test.describe("Mapeamento Arlo ↔ SGD — Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("exibe os campos obrigatórios do seed com a tag correspondente", async ({ page }) => {
    await abrir(page);
    const linha = page.getByTestId("arlo-linha-demanda_id");
    await expect(linha.getByText("Obrigatório")).toBeVisible();
    await expect(linha.getByText("ID da demanda")).toBeVisible();
  });

  test("mostra o aviso de preview enquanto o endpoint não existe", async ({ page }) => {
    await abrir(page);
    await expect(page.getByTestId("arlo-preview-pendente")).toBeVisible();
    await expect(
      page.getByText("Preview aguardando o backend"),
    ).toBeVisible();
  });

  test("troca para a aba de importação ao clicar na segunda tab", async ({ page }) => {
    await abrir(page);
    await page.getByTestId("arlo-tab-importacao").click();
    await expect(
      page.getByTestId("arlo-linha-data_pagamento"),
    ).toBeVisible();
  });

  test("reordena uma linha para cima e persiste a nova ordem", async ({ page }) => {
    // Preserva a ordem original para desfazer no final: a tela é escrita e
    // outros specs do mapeamento rodam no mesmo seed.
    await abrir(page);
    const linhasAntes = await page.locator('tr[data-testid^="arlo-linha-"]').all();
    const camposAntes: string[] = [];
    for (const linha of linhasAntes) {
      camposAntes.push((await linha.getAttribute("data-testid"))!.replace("arlo-linha-", ""));
    }

    // Primeira linha (`demanda_id`, obrigatória) já está no topo; movimentação
    // real: pega a SEGUNDA linha e sobe uma posição.
    const alvo = camposAntes[1];
    const linhaAlvo = page.getByTestId(`arlo-linha-${alvo}`);
    const promessaReorder = page.waitForResponse(
      (r) => REORDENAR_API.test(r.url()) && r.status() === 200,
    );
    await linhaAlvo.getByRole("button", { name: /mover.*para cima/i }).click();
    await promessaReorder;

    // Depois do reorder a ordem no DOM reflete a nova ordem.
    const linhasDepois = await page.locator('tr[data-testid^="arlo-linha-"]').all();
    const camposDepois: string[] = [];
    for (const linha of linhasDepois) {
      camposDepois.push((await linha.getAttribute("data-testid"))!.replace("arlo-linha-", ""));
    }
    expect(camposDepois[0]).toBe(alvo);
    expect(camposDepois[1]).toBe(camposAntes[0]);

    // Devolve a ordem anterior ao seed, para não contaminar o próximo spec.
    const restaurar = page.waitForResponse(
      (r) => REORDENAR_API.test(r.url()) && r.status() === 200,
    );
    await linhaAlvo.getByRole("button", { name: /mover.*para baixo/i }).click();
    await restaurar;
  });
});

test.describe("Mapeamento Arlo ↔ SGD — fora do Super Admin", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("mostra tela de restrição para quem não é Super Admin", async ({ page }) => {
    await page.goto(PAGE_URL);
    // O gate do front mostra o <RestrictedAccess/>. Também cobre o 403 que o
    // backend aplicaria no CRUD, porque antes de chamar a API a tela desvia.
    await expect(page.getByText(/restrit|permissão/i).first()).toBeVisible();
  });
});
