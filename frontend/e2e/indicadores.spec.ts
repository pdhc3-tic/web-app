import { expect, test, type Page } from "@playwright/test";
import {
  criarIndicadoresFixture,
  indicadorNoBanco,
  PREFIXO,
  removerIndicadoresFixture,
  type IndicadorEmUso,
} from "./helpers/indicadoresFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Catálogo de Indicadores (#453), contra o backend real: a UGP cadastra,
 * edita, inativa e exclui um indicador da própria suíte; num indicador do seed
 * que já tem Ação, o backend recusa a exclusão e pede confirmação para trocar a
 * forma de apuração, e a tela mostra as duas coisas sem gravar nada nele.
 */

let emUso: IndicadorEmUso;
const CODIGO = `${PREFIXO}FAM`;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  emUso = criarIndicadoresFixture();
});

test.afterAll(() => {
  removerIndicadoresFixture();
});

async function escolher(page: Page, id: string, opcao: string) {
  await page.locator(`button#${id}`).click();
  await page.getByRole("option", { name: opcao, exact: true }).first().click();
}

async function buscar(page: Page, termo: string) {
  await page.getByTestId("indicadores-busca").fill(termo);
}

/** O id do indicador a partir da linha da tabela. */
async function idDaLinha(page: Page, codigo: string): Promise<string> {
  const linha = page.locator('[data-testid^="indicador-linha-"]').filter({ hasText: codigo }).first();
  await expect(linha).toBeVisible();
  return (await linha.getAttribute("data-testid"))!.replace("indicador-linha-", "");
}

test.describe("UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("a home do SGP leva ao catálogo", async ({ page }) => {
    await page.goto("/sgp");
    await page.getByRole("link", { name: /Catálogo de Indicadores/ }).click();
    await expect(page).toHaveURL(/\/sgp\/indicadores/);
    await expect(page.getByTestId("indicadores-table")).toBeVisible();
  });

  test("cadastra, edita, inativa e exclui um indicador", async ({ page }) => {
    await page.goto("/sgp/indicadores");
    await page.getByTestId("indicador-novo-btn").click();
    const form = page.getByTestId("indicador-form");
    await form.getByTestId("indicador-form-codigo").fill(CODIGO);
    await form.getByTestId("indicador-form-nome").fill("Famílias com plano produtivo");
    await escolher(page, "indicador-form-unidade", "Família");
    await escolher(page, "indicador-form-categoria", "Gestão");
    await escolher(page, "indicador-form-forma", "Soma de UFPAs vinculadas");
    await form.getByLabel("Gênero", { exact: true }).check();
    await page.getByTestId("indicador-form-salvar").click();
    await expect(form).toHaveCount(0);
    expect(indicadorNoBanco(CODIGO)).toEqual({ nome: "Famílias com plano produtivo", forma: "soma_ufpas", ativo: true });

    await buscar(page, CODIGO);
    const id = await idDaLinha(page, CODIGO);
    const linha = page.getByTestId(`indicador-linha-${id}`);
    await expect(linha).toContainText("Soma de UFPAs vinculadas");
    await expect(linha).toContainText("Gênero");

    // Editar: sem Ações, a troca de forma não pede confirmação.
    await page.getByTestId(`indicador-editar-${id}`).click();
    await form.getByTestId("indicador-form-nome").fill("Famílias com plano produtivo aprovado");
    await escolher(page, "indicador-form-forma", "Lançamento manual pela UGP");
    await page.getByTestId("indicador-form-salvar").click();
    await expect(form).toHaveCount(0);
    await expect(linha).toContainText("Famílias com plano produtivo aprovado");
    expect(indicadorNoBanco(CODIGO)?.forma).toBe("manual");

    // Inativar: sai da lista padrão (só ativos) e aparece em "Inativos".
    await page.getByTestId(`indicador-ativo-${id}`).click();
    await expect(linha).toHaveCount(0);
    expect(indicadorNoBanco(CODIGO)?.ativo).toBe(false);
    await escolher(page, "indicadores-situacao", "Inativos");
    await expect(linha).toContainText("Inativo");

    // Excluir: sem Ações, sai do banco.
    await page.getByTestId(`indicador-excluir-${id}`).click();
    await page.getByTestId("indicador-excluir-confirmar").click();
    await expect(linha).toHaveCount(0);
    expect(indicadorNoBanco(CODIGO)).toBeNull();
  });

  test("indicador em uso: não exclui e a troca de forma pede confirmação", async ({ page }) => {
    await page.goto("/sgp/indicadores");
    await buscar(page, emUso.codigo);
    const id = await idDaLinha(page, emUso.codigo);

    await page.getByTestId(`indicador-excluir-${id}`).click();
    await page.getByTestId("indicador-excluir-confirmar").click();
    await expect(page.getByTestId("indicador-exclusao")).toContainText("não pode ser excluído");
    await expect(page.getByTestId("indicador-excluir-confirmar")).toHaveText("Inativar");
    await page.getByRole("button", { name: "Cancelar" }).click();

    const forma = emUso.formaApuracao === "manual" ? "Soma de participantes" : "Lançamento manual pela UGP";
    await page.getByTestId(`indicador-editar-${id}`).click();
    await escolher(page, "indicador-form-forma", forma);
    await page.getByTestId("indicador-form-salvar").click();
    await expect(page.getByTestId("indicador-recalculo")).toContainText(`${emUso.acoes} Ação(ões)`);
    await page.getByRole("button", { name: "Voltar" }).click();
    await expect(page.getByTestId("indicador-recalculo")).toHaveCount(0);

    // Nada foi gravado no indicador do seed.
    expect(indicadorNoBanco(emUso.codigo)).toMatchObject({ forma: emUso.formaApuracao, ativo: true });
  });
});

test.describe("ADT", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("vê o catálogo sem as ações de escrita", async ({ page }) => {
    await page.goto("/sgp/indicadores");
    await expect(page.locator('[data-testid^="indicador-linha-"]').first()).toBeVisible();
    await expect(page.getByTestId("indicador-novo-btn")).toHaveCount(0);
    await expect(page.locator('[data-testid^="indicador-editar-"]')).toHaveCount(0);
  });
});
