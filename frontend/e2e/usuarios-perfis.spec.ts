import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { abrirComApi, apiGet } from "./helpers/apiReal";
import { storageStatePath } from "./helpers/users";

/**
 * #405 (AJ-FE-09) — Perfis operacionais no cadastro de usuários, contra o
 * backend real (`POST /users/` com `perfis_input`, `GET /roles/`).
 *
 * O usuário criado tem e-mail com prefixo próprio e é apagado no fim.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const EMAIL = "e2e-405.operacional@demo.pdhc.local";
const NOME = "E2E-405 Coordenadora de Evento";

function apagarUsuarioDoTeste(): void {
  execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "backend",
      "sh",
      "-c",
      'DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD python manage.py shell -c "$1"',
      "sh",
      `from django.contrib.auth import get_user_model\nget_user_model().objects.filter(email="${EMAIL}").delete()`,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

type PerfilApi = { id: number; nome: string; slug: string; categoria: "principal" | "operacional" };

test.describe.configure({ mode: "serial" });
test.use({ storageState: storageStatePath("superAdmin") });

test.beforeAll(apagarUsuarioDoTeste);
test.afterAll(apagarUsuarioDoTeste);

test("o formulário separa principais e operacionais, e o objeto só existe no operacional", async ({ page }) => {
  await page.goto("/admin/usuarios");
  await page.getByRole("button", { name: "Novo usuário" }).first().click();
  const form = page.getByTestId("novo-usuario-form");
  await expect(form).toBeVisible();

  await expect(form.getByTestId("perfis-principais")).toContainText("Perfis principais");
  await expect(form.getByTestId("perfis-operacionais")).toContainText("Perfis operacionais");
  await expect(form.locator('[data-testid$="-objeto"]')).toHaveCount(0);

  await form.getByTestId("perfil-operacional-adicionar").click();
  await expect(form.getByTestId("perfil-operacional-0-objeto")).toBeVisible();
  await expect(form.getByTestId("perfis-principais").locator('[data-testid$="-objeto"]')).toHaveCount(0);
});

test("cria usuário com perfil principal e operacional, e o backend guarda o objeto", async ({ page }) => {
  const origem = await abrirComApi(page, "/admin/usuarios");
  const { results: perfis } = await apiGet<{ results: PerfilApi[] }>(
    page,
    origem,
    "/api/v1/roles/?limit=200&ativo=true",
  );
  const principal = perfis.find((p) => p.slug === "ugp")!;
  const operacional = perfis.find((p) => p.slug === "coordenador-evento")!;

  await page.getByRole("button", { name: "Novo usuário" }).first().click();
  const form = page.getByTestId("novo-usuario-form");
  await form.getByLabel("Nome completo").fill(NOME);
  await form.getByLabel("E-mail").fill(EMAIL);

  await form.getByTestId("perfil-principal-0").getByRole("combobox").first().click();
  await page.getByRole("option", { name: principal.nome, exact: true }).click();

  await form.getByTestId("perfil-operacional-adicionar").click();
  await form.getByTestId("perfil-operacional-0").getByRole("combobox").first().click();
  await page.getByRole("option", { name: operacional.nome, exact: true }).click();
  await form.getByLabel(/Evento \(número\)/).fill("12");

  const criacao = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/v1/users/" && r.request().method() === "POST",
  );
  await form.getByTestId("novo-usuario-salvar").click();
  const resposta = await criacao;
  expect(resposta.status()).toBe(201);

  const enviado = JSON.parse(resposta.request().postData() ?? "{}") as {
    perfis_input: { perfil_id: number; objeto_tipo: string | null; objeto_id: number | null }[];
  };
  expect(enviado.perfis_input).toContainEqual(
    expect.objectContaining({ perfil_id: operacional.id, objeto_tipo: "evento", objeto_id: 12 }),
  );
  await expect(form).toHaveCount(0);

  await page.getByLabel("Buscar").fill("E2E-405");
  await expect(page.getByText(NOME)).toBeVisible();
});

test("o filtro de categoria recorta os perfis oferecidos", async ({ page }) => {
  const origem = await abrirComApi(page, "/admin/usuarios");
  const { results: perfis } = await apiGet<{ results: PerfilApi[] }>(
    page,
    origem,
    "/api/v1/roles/?limit=200&ativo=true",
  );
  const operacionais = perfis.filter((p) => p.categoria === "operacional").map((p) => p.nome);
  const principal = perfis.find((p) => p.categoria === "principal")!;

  await page.getByTestId("usuarios-filtro-categoria").getByRole("combobox").click();
  await page.getByRole("option", { name: "Operacionais", exact: true }).click();
  await expect(page).toHaveURL(/categoria=operacional/);

  await page.getByTestId("usuarios-filtro-perfil").getByRole("combobox").click();
  for (const nome of operacionais) {
    await expect(page.getByRole("option", { name: nome, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("option", { name: principal.nome, exact: true })).toHaveCount(0);
});
