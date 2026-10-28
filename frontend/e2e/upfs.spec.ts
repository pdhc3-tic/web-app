import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import {
  cpfValido,
  PREFIXO_UPF_E2E,
  primeiroUpfId,
  removerUpfsDoWizard,
} from "./helpers/upf";

/**
 * Wizard de cadastro de UPF contra o backend real: estados, municípios e
 * projetos vêm da API, e a UPF criada no fluxo completo é apagada no
 * teardown (`removerUpfsDoWizard`, pelo prefixo do titular).
 */

/** Estado do seed usado nos fluxos — o `seed_demo` cria os sete do projeto. */
const ESTADO = /Rio Grande do Norte/i;

const DRAFT_NOVA = "sgp.upf.draft.novo";

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  removerUpfsDoWizard();
});

test.afterAll(() => {
  removerUpfsDoWizard();
});

/** O passo atual é o botão do Stepper com `aria-current="step"`. */
async function esperarPasso(page: Page, nome: string) {
  await expect(page.locator('[aria-current="step"]')).toHaveText(new RegExp(nome));
}

/** Abre um `Select` do design system pelo rótulo e escolhe a opção. */
async function escolher(page: Page, rotulo: RegExp, opcao: string | RegExp) {
  const combo = page.getByRole("combobox", { name: rotulo });
  await expect(combo).toBeEnabled();
  await combo.click();
  await page.getByRole("option", { name: opcao }).first().click();
}

/** Preenche a Localização com dados reais: Estado, primeiro município e projeto. */
async function preencherLocalizacao(page: Page) {
  await escolher(page, /^Estado/, ESTADO);
  await escolher(page, /^Município/, /.+/);
  await escolher(page, /^Projeto/, /.+/);
}

/** Espera o rascunho debounced chegar ao localStorage. */
async function esperarRascunho(page: Page) {
  await expect
    .poll(() => page.evaluate((chave) => window.localStorage.getItem(chave), DRAFT_NOVA))
    .not.toBeNull();
}

async function abrirNova(page: Page) {
  await page.goto("/sgp/upfs/nova");
  await esperarPasso(page, "Localização");
  await expect(page.getByRole("combobox", { name: /^Estado/ })).toBeEnabled();
}

test.describe("SGP — Wizard de cadastro de UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test.beforeEach(async ({ page }) => {
    // Um rascunho de outro teste faria o wizard abrir com a oferta de continuar.
    await page.addInitScript((chave) => {
      if (!sessionStorage.getItem("e2e-rascunho-limpo")) {
        localStorage.removeItem(chave);
        sessionStorage.setItem("e2e-rascunho-limpo", "1");
      }
    }, DRAFT_NOVA);
  });

  test("passo 0 valida estado, município e projeto antes de avançar", async ({ page }) => {
    await abrirNova(page);

    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Selecione o estado.")).toBeVisible();
    await expect(page.getByText("Selecione o município.")).toBeVisible();
    await expect(page.getByText("Selecione o projeto.")).toBeVisible();
    await esperarPasso(page, "Localização");
  });

  test("passo 1 valida nome e CPF do titular", async ({ page }) => {
    await abrirNova(page);
    await preencherLocalizacao(page);
    await page.getByRole("button", { name: "Avançar" }).click();

    await esperarPasso(page, "Dados Básicos");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Informe o nome do titular.")).toBeVisible();
    await expect(page.getByText("Informe o CPF.")).toBeVisible();
  });

  test("CPF inválido bloqueia o avanço do passo 1", async ({ page }) => {
    await abrirNova(page);
    await preencherLocalizacao(page);
    await page.getByRole("button", { name: "Avançar" }).click();

    await esperarPasso(page, "Dados Básicos");
    await page.getByLabel(/^Nome do titular/).fill("João Silva");
    await page.getByLabel(/^CPF/).fill("00000000000");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("CPF inválido.")).toBeVisible();
    await esperarPasso(page, "Dados Básicos");
  });

  test("rascunho é salvo no localStorage e ofertado ao revisitar", async ({ page }) => {
    await abrirNova(page);
    await escolher(page, /^Estado/, ESTADO);
    await esperarRascunho(page);

    await page.goto("/sgp/atividades");
    await page.goto("/sgp/upfs/nova");

    await expect(page.getByRole("button", { name: /Continuar rascunho/i })).toBeVisible();
  });

  test("continuar rascunho restaura todos os valores do passo 0", async ({ page }) => {
    await abrirNova(page);
    await preencherLocalizacao(page);
    await esperarRascunho(page);

    await page.goto("/sgp/atividades");
    await page.goto("/sgp/upfs/nova");

    const continuar = page.getByRole("button", { name: /Continuar rascunho/i });
    await expect(continuar).toBeVisible();
    await continuar.click();

    // Restaurado, o passo 0 já é válido: avança sem erro.
    await expect(page.getByRole("combobox", { name: /^Estado/ })).toHaveText(ESTADO);
    await page.getByRole("button", { name: "Avançar" }).click();
    await esperarPasso(page, "Dados Básicos");
  });

  test("descartar rascunho limpa o formulário", async ({ page }) => {
    await abrirNova(page);
    await escolher(page, /^Estado/, ESTADO);
    await esperarRascunho(page);
    await page.goto("/sgp/upfs/nova");

    await page.getByRole("button", { name: /Descartar/i }).first().click();

    await expect(page.getByRole("button", { name: /Continuar rascunho/i })).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: /^Estado/ })).toHaveText(/Selecione o estado/i);
  });

  test("wizard completo cria UPF no backend e redireciona para a ficha", async ({ page }) => {
    const nome = `${PREFIXO_UPF_E2E} Titular`;

    await abrirNova(page);
    await preencherLocalizacao(page);
    await page.getByRole("button", { name: "Avançar" }).click();

    await esperarPasso(page, "Dados Básicos");
    await page.getByLabel(/^Nome do titular/).fill(nome);
    await page.getByLabel(/^CPF/).fill(cpfValido());
    await page.getByRole("button", { name: "Avançar" }).click();

    await esperarPasso(page, "Comunicação");
    await page.getByRole("button", { name: "Avançar" }).click();

    await esperarPasso(page, "Moradia");
    const criacao = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/v1/upfs/" && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    const resposta = await criacao;
    expect(resposta.status()).toBe(201);
    const { id } = (await resposta.json()) as { id: number };

    await page.waitForURL(new RegExp(`/sgp/upfs/${id}/?$`));
    await expect(page.getByRole("heading", { level: 1 })).toContainText(nome);
  });

  test("edição de UPF existente pré-carrega os campos", async ({ page }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}/editar`);

    await esperarPasso(page, "Localização");
    await expect(page.getByRole("combobox", { name: /^Estado/ })).not.toHaveText(/Selecione/i);
    await expect(page.getByRole("combobox", { name: /^Município/ })).not.toHaveText(/Selecione|Escolha/i);

    await page.getByRole("button", { name: "Avançar" }).click();
    await esperarPasso(page, "Dados Básicos");
    await expect(page.getByLabel(/^Nome do titular/)).not.toHaveValue("");
    await expect(page.getByLabel(/^CPF/)).not.toHaveValue("");
  });
});
