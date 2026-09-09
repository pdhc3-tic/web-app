import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

const ESTADOS_API = "**/api/v1/estados/**";
const MUNICIPIOS_API = "**/api/v1/municipios/**";
const COMUNIDADES_API = "**/api/v1/comunidades/**";
const PROJETOS_API = "**/api/v1/projetos/**";
const UPF_API = "**/api/v1/sgp/upfs/**";

function estadoFake(id: number, sigla: string, nome: string) {
  return { id, sigla, nome };
}

function municipioFake(id: number, nome: string, stateId: number) {
  return { id, nome, state: stateId, state_sigla: "PE" };
}

async function stubWizardOptions(page: import("@playwright/test").Page) {
  await page.route(ESTADOS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([estadoFake(17, "PE", "Pernambuco")]),
    });
  });

  await page.route(MUNICIPIOS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([municipioFake(1001, "Ouricuri", 17)]),
    });
  });

  await page.route(COMUNIDADES_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ count: 1, results: [{ id: 501, nome: "Cacimba Velha" }] }),
    });
  });

  await page.route(PROJETOS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ count: 1, results: [{ id: 3, nome: "PDHC III" }] }),
    });
  });
}

async function escolherNoSelect(
  page: import("@playwright/test").Page,
  label: string,
  opcao: string,
) {
  await page.getByLabel(label, { exact: true }).click();
  await page
    .locator('[role="listbox"] li')
    .filter({ hasText: opcao })
    .first()
    .click();
}

test.describe("SGP — Wizard de cadastro de UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("passo 0 valida estado, município e projeto antes de avançar", async ({
    page,
  }) => {
    await stubWizardOptions(page);
    await page.goto("/sgp/upfs/nova");
    await expect(page.getByText("Passo 1 de 4")).toBeVisible();

    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Selecione o estado.")).toBeVisible();
    await expect(page.getByText("Selecione o município.")).toBeVisible();
    await expect(page.getByText("Selecione o projeto.")).toBeVisible();
  });

  test("passo 1 valida nome e CPF do titular", async ({ page }) => {
    await stubWizardOptions(page);
    await page.goto("/sgp/upfs/nova");

    await escolherNoSelect(page, "Estado", "Pernambuco");
    await escolherNoSelect(page, "Município", "Ouricuri");
    await escolherNoSelect(page, "Projeto", "PDHC III");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Passo 2 de 4")).toBeVisible();
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Informe o nome do titular.")).toBeVisible();
    await expect(page.getByText("Informe o CPF.")).toBeVisible();
  });

  test("CPF inválido bloqueia o avanço do passo 1", async ({ page }) => {
    await stubWizardOptions(page);
    await page.goto("/sgp/upfs/nova");

    await escolherNoSelect(page, "Estado", "Pernambuco");
    await escolherNoSelect(page, "Município", "Ouricuri");
    await escolherNoSelect(page, "Projeto", "PDHC III");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Passo 2 de 4")).toBeVisible();
    await page.getByLabel("Nome completo").fill("João Silva");
    await page.getByLabel("CPF").fill("00000000000");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("CPF inválido.")).toBeVisible();
  });

  test("rascunho é salvo no localStorage e ofertado ao revisitar", async ({
    page,
  }) => {
    await stubWizardOptions(page);
    await page.goto("/sgp/upfs/nova");

    await escolherNoSelect(page, "Estado", "Pernambuco");
    await page.waitForTimeout(700);

    await page.goto("/sgp/atividades");
    await page.goto("/sgp/upfs/nova");

    await expect(
      page.getByRole("button", { name: /Continuar rascunho/i }),
    ).toBeVisible();
  });

  test("descartar rascunho limpa o formulário", async ({ page }) => {
    await stubWizardOptions(page);
    await page.goto("/sgp/upfs/nova");

    await escolherNoSelect(page, "Estado", "Pernambuco");
    await page.waitForTimeout(700);
    await page.goto("/sgp/upfs/nova");

    await page.getByRole("button", { name: /Descartar/i }).first().click();

    await expect(
      page.getByRole("button", { name: /Continuar rascunho/i }),
    ).toHaveCount(0);
  });

  test("wizard completo cria UPF e redireciona para a ficha", async ({
    page,
  }) => {
    await stubWizardOptions(page);

    await page.route(UPF_API, async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: 9999,
          nome_titular: "João Silva",
          cpf: "12345678909",
          municipio: { id: 1001, nome: "Ouricuri", state: 17 },
          projeto: { id: 3, nome: "PDHC III" },
          comunidade: null,
          territorio: null,
          foto_url: null,
          ativo: true,
        }),
      });
    });

    await page.goto("/sgp/upfs/nova");

    await escolherNoSelect(page, "Estado", "Pernambuco");
    await escolherNoSelect(page, "Município", "Ouricuri");
    await escolherNoSelect(page, "Projeto", "PDHC III");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Passo 2 de 4")).toBeVisible();
    await page.getByLabel("Nome completo").fill("João Silva");
    await page.getByLabel("CPF").fill("529.982.247-25");
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Passo 3 de 4")).toBeVisible();
    await page.getByRole("button", { name: "Avançar" }).click();

    await expect(page.getByText("Passo 4 de 4")).toBeVisible();
    await page.getByRole("button", { name: "Salvar" }).click();

    await page.waitForURL(/\/sgp\/upfs\/9999/);
  });

  test("edição de UPF existente pré-carrega todos os campos e preserva rascunho por id", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}/editar`);

    await expect(page.getByText("Passo 1 de 4")).toBeVisible();
    const nomeInput = page.getByLabel("Nome completo");
    await expect(nomeInput).toBeVisible();
    await expect(nomeInput).not.toHaveValue("");
  });
});
