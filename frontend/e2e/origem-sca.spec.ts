import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Badge "Registrado via SCA" (FE-12).
 *
 * A regra é `ultima_origem === "sca"`, e não `device_id` preenchido: o
 * `device_id` fica gravado para sempre depois do primeiro sync, e usá-lo faria
 * a badge continuar aparecendo depois de uma edição pela web — o oposto do que
 * o critério de "origem da versão mais recente" pede. Os viewsets do SGP gravam
 * `ultima_origem="web"` em todo create e update, então o campo acompanha mesmo
 * a última edição.
 *
 * As fixtures vêm do seed: `--sca-only` marca uma UPF e uma Atividade como
 * originadas no aplicativo; todo o resto da demonstração fica como "web". Os ids
 * são lidos do banco porque o seed não garante quais registros recebem a marca.
 */

function consultar(sql: string): string {
  return execFileSync(
    "docker",
    ["exec", "db", "psql", "-U", "postgres", "-d", "app_db", "-tAc", sql],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
}

function recriarFixturesSca(): void {
  execFileSync(
    "docker",
    ["exec", "backend", "python", "manage.py", "seed_demo", "--sca-only"],
    { stdio: "pipe", timeout: 120_000 },
  );
}

function primeiroId(tabela: string, origem: "sca" | "web"): number {
  const linha = consultar(
    `select id from ${tabela} where ultima_origem='${origem}' order by id limit 1;`,
  );
  const id = Number(linha);
  expect(id, `nenhum registro em ${tabela} com origem ${origem}`).toBeGreaterThan(0);
  return id;
}

function badge(page: Page) {
  return page.getByTestId("badge-origem-sca");
}

// Os testes deste arquivo são todos de leitura: basta garantir que existe um
// registro marcado como originado no aplicativo. Recriar por teste só somaria
// tempo de Django sem mudar o que é verificado.
test.beforeAll(() => {
  recriarFixturesSca();
});

test.describe("Procedência SCA — UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("UPF originada no aplicativo exibe a badge com a data da sincronização", async ({
    page,
  }) => {
    const id = primeiroId("sgp_upf", "sca");

    await page.goto(`/sgp/upfs/${id}`);
    await expect(badge(page)).toBeVisible();
    await expect(badge(page)).toContainText("Registrado via SCA");

    // O tooltip carrega a data/hora do sync — é o que distingue esta badge de
    // um rótulo estático.
    await expect(badge(page)).toHaveAttribute(
      "title",
      /^Sincronizado em \d{2}\/\d{2}\/\d{4} \d{2}:\d{2} \(.+\)$/,
    );
  });

  test("UPF cadastrada pela web não exibe a badge", async ({ page }) => {
    const id = primeiroId("sgp_upf", "web");

    await page.goto(`/sgp/upfs/${id}`);
    // Esperar a ficha carregar antes de afirmar a ausência: sem isto o teste
    // passaria com a página ainda vazia.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(badge(page)).toHaveCount(0);
  });
});

test.describe("Procedência SCA — Atividade", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("atividade originada no aplicativo exibe a badge na ficha", async ({
    page,
  }) => {
    const id = primeiroId("sgp_activity", "sca");

    await page.goto(`/sgp/atividades/${id}`);
    await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();
    await expect(badge(page)).toBeVisible();
    await expect(badge(page)).toHaveAttribute(
      "title",
      /^Sincronizado em \d{2}\/\d{2}\/\d{4}/,
    );
  });

  test("atividade cadastrada pela web não exibe a badge", async ({ page }) => {
    const id = primeiroId("sgp_activity", "web");

    await page.goto(`/sgp/atividades/${id}`);
    await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();
    await expect(badge(page)).toHaveCount(0);
  });

  test("clicar na atividade abre a ficha, e o botão Editar leva ao formulário", async ({
    page,
  }) => {
    // A lista levava direto ao formulário de edição; agora consulta e edição são
    // caminhos distintos.
    await page.goto("/sgp/atividades");
    // `tabindex=0` isola a linha clicável: enquanto carrega, a tabela renderiza
    // linhas de esqueleto que também são <tr> e não respondem ao clique.
    const linha = page.locator('tbody tr[tabindex="0"]').first();
    await expect(linha).toBeVisible();
    await linha.click();

    await page.waitForURL(/\/sgp\/atividades\/\d+\/?$/);
    await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();

    await page.getByTestId("atividade-editar-btn").click();
    await page.waitForURL(/\/sgp\/atividades\/\d+\/editar\/?$/);
  });
});
