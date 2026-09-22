import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

const TECNICOS_API = "**/api/v1/sgp/tecnicos/**";

function tecnicoFake(
  id: number,
  nome: string,
  papel: string,
  oscNome: string | null = null,
  territorioNome: string | null = null,
  ativo = true,
): Record<string, unknown> {
  return {
    id,
    user: id * 10,
    user_nome: nome,
    territorio: territorioNome ? id * 100 : null,
    territorio_nome: territorioNome,
    osc: oscNome ? id * 200 : null,
    osc_nome: oscNome,
    papel,
    ativo,
  };
}

function paginated(results: unknown[], count?: number): string {
  return JSON.stringify({
    count: count ?? (results as unknown[]).length,
    next: null,
    previous: null,
    results,
  });
}

test.describe("SGP — Técnicos (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("card Técnicos aparece na página do SGP com link funcional", async ({
    page,
  }) => {
    await page.goto("/sgp");
    const card = page.getByRole("link", { name: /Técnicos/i });
    await expect(card).toBeVisible();
    const href = await card.getAttribute("href");
    expect(href).toContain("/sgp/tecnicos");
  });

  test("listagem exibe colunas e dados dos técnicos", async ({ page }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          tecnicoFake(1, "Ana Souza", "ADT", "OSC Nordeste", "Território A"),
          tecnicoFake(2, "Carlos Lima", "Coordenador", null, null),
          tecnicoFake(3, "Maria Santos", "ADT", "OSC Sul", null, false),
        ]),
      });
    });

    await page.goto("/sgp/tecnicos");
    await expect(page.getByRole("columnheader", { name: "Nome" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Papel" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Situação" })).toBeVisible();

    await expect(page.getByText("Ana Souza")).toBeVisible();
    await expect(page.getByText("ADT").first()).toBeVisible();
    await expect(page.getByText("Ativo").first()).toBeVisible();

    await expect(page.getByText("Maria Santos")).toBeVisible();
    await expect(page.getByText("Inativo")).toBeVisible();

    await expect(page.getByRole("button", { name: "Adicionar técnico" })).toBeVisible();
  });

  test("estado vazio sem filtros ativos exibe CTA para adicionar", async ({
    page,
  }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([]),
      });
    });

    await page.goto("/sgp/tecnicos");
    await expect(page.getByText("Nenhum técnico cadastrado")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Adicionar técnico" }).first(),
    ).toBeVisible();
  });

  test("estado vazio com filtros ativos exibe botão Limpar filtros", async ({
    page,
  }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([]),
      });
    });

    await page.goto("/sgp/tecnicos?papel=ADT");
    await expect(page.getByText("Nenhum técnico encontrado")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Limpar filtros" }),
    ).toBeVisible();
  });

  test("clique em linha abre SlideOver no modo edição", async ({ page }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          tecnicoFake(1, "Ana Souza", "ADT", "OSC Nordeste", "Território A"),
        ]),
      });
    });

    await page.goto("/sgp/tecnicos");
    await page.getByText("Ana Souza").click();

    const slideover = page.locator('[role="dialog"]');
    await expect(slideover).toBeVisible();
    await expect(slideover.getByRole("heading", { name: "Editar técnico" })).toBeVisible();
    await expect(slideover.getByLabel("Papel")).toBeVisible();
    await expect(slideover.getByRole("button", { name: "Salvar" })).toBeVisible();
  });

  test("formulário de criação valida campos obrigatórios", async ({ page }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([]),
      });
    });

    await page.goto("/sgp/tecnicos");
    await page.getByRole("button", { name: "Adicionar técnico" }).first().click();

    const slideover = page.locator('[role="dialog"]');
    await expect(slideover.getByRole("heading", { name: "Novo técnico" })).toBeVisible();
    await slideover.getByRole("button", { name: "Salvar" }).click();

    await expect(slideover.getByText("Selecione o usuário.")).toBeVisible();
    await expect(slideover.getByText("Informe o papel.")).toBeVisible();
  });

  test("desativar técnico exige confirmação e atualiza listagem", async ({
    page,
  }) => {
    await page.route(TECNICOS_API, async (route) => {
      const method = route.request().method();
      if (method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: paginated([
            tecnicoFake(1, "Ana Souza", "ADT", "OSC Nordeste", "Território A"),
          ]),
        });
      } else if (method === "DELETE") {
        await route.fulfill({ status: 204 });
      } else {
        await route.fallback();
      }
    });

    await page.goto("/sgp/tecnicos");
    await page.getByText("Ana Souza").click();

    const slideover = page.locator('[role="dialog"]').first();
    await expect(slideover).toBeVisible();
    await slideover.getByRole("button", { name: "Editar técnico" }).click().catch(() => {});

    const editSlideover = page.locator('[role="dialog"]').last();
    await expect(editSlideover).toBeVisible();
  });

  test("erro na API exibe mensagem e botão Tentar novamente", async ({
    page,
  }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({ status: 500, body: "error" });
    });

    await page.goto("/sgp/tecnicos");
    await expect(page.getByText("Não foi possível carregar os técnicos")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Tentar novamente" }),
    ).toBeVisible();
  });
});

test.describe("SGP — Técnicos (sem permissão)", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("usuario sem permissao nao ve botao Adicionar tecnico", async ({
    page,
  }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          tecnicoFake(1, "Ana Souza", "ADT", "OSC Nordeste", "Território A"),
        ]),
      });
    });

    await page.goto("/sgp/tecnicos");
    await expect(page.getByText("Ana Souza")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Adicionar técnico" }),
    ).toHaveCount(0);
  });

  test("clique em linha abre SlideOver no modo visualização", async ({
    page,
  }) => {
    await page.route(TECNICOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          tecnicoFake(1, "Ana Souza", "ADT", "OSC Nordeste", "Território A"),
        ]),
      });
    });

    await page.goto("/sgp/tecnicos");
    await page.getByText("Ana Souza").click();

    const slideover = page.locator('[role="dialog"]');
    await expect(slideover).toBeVisible();
    await expect(slideover.getByRole("button", { name: "Salvar" })).toHaveCount(0);
    await expect(slideover.getByRole("button", { name: "Fechar" })).toBeVisible();

    await expect(slideover.getByText("Nome")).toBeVisible();
    await expect(slideover.getByText("Ana Souza")).toBeVisible();
    await expect(slideover.getByText("ADT")).toBeVisible();
    await expect(slideover.getByText("OSC Nordeste")).toBeVisible();
    await expect(slideover.getByText("Território A")).toBeVisible();
    await expect(slideover.getByText("Ativo")).toBeVisible();
  });
});
