import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #406 (AJ-FE-10) — Desativação de usuário com aviso de impacto, contra o
 * backend real (`GET /core/usuarios/{id}/impacto-desativacao/` e
 * `DELETE /users/{id}/`).
 *
 * O usuário do teste é criado aqui, sem demandas, e apagado no fim: desativar
 * alguém do seed mudaria os dados das outras specs. A lista de demandas
 * canceladas e o saldo por rubrica estão no teste de componente do diálogo.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const EMAIL = "e2e-406.desativar@demo.pdhc.local";
const NOME = "E2E-406 Pessoa a Desativar";

function djangoShell(script: string): string {
  return execFileSync(
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
      script,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

const APAGAR = `
from django.contrib.auth import get_user_model
get_user_model().objects.filter(email="${EMAIL}").delete()
`;

const CRIAR = `${APAGAR}
from apps.core.models import Role, UserProfile
U = get_user_model()
u = U.objects.create(email="${EMAIL}", nome="${NOME}", ativo=True)
UserProfile.objects.create(user=u, perfil=Role.objects.get(slug="ugp"))
print("E2E_406_USER", u.pk)
`;

let userId: number;

test.describe.configure({ mode: "serial" });
test.use({ storageState: storageStatePath("superAdmin") });

test.beforeAll(() => {
  const linha = djangoShell(CRIAR)
    .split("\n")
    .find((l) => l.startsWith("E2E_406_USER "));
  if (!linha) throw new Error("Fixture da #406 não criou o usuário.");
  userId = Number(linha.trim().split(" ")[1]);
});

test.afterAll(() => {
  djangoShell(APAGAR);
});

test("o diálogo mostra o impacto e só desativa depois da confirmação explícita", async ({ page }) => {
  await page.goto("/admin/usuarios");
  await page.getByLabel("Buscar").fill("E2E-406");
  await expect(page.getByText(NOME)).toBeVisible();

  const impacto = page.waitForResponse((r) =>
    new URL(r.url()).pathname.endsWith(`/core/usuarios/${userId}/impacto-desativacao/`),
  );
  await page.getByTestId(`usuario-desativar-${userId}`).click();
  expect((await impacto).status()).toBe(200);

  const dialogo = page.getByTestId("desativar-usuario-dialog");
  await expect(dialogo).toContainText(NOME);
  await expect(dialogo.getByTestId("desativar-sem-impacto")).toBeVisible();

  const confirmar = page.getByTestId("desativar-confirmar");
  await expect(confirmar).toBeDisabled();

  await dialogo.getByTestId("desativar-ciente").check();
  await expect(confirmar).toBeEnabled();

  const desativacao = page.waitForResponse(
    (r) => new URL(r.url()).pathname === `/api/v1/users/${userId}/` && r.request().method() === "DELETE",
  );
  await confirmar.click();
  expect((await desativacao).status()).toBe(204);

  // A listagem padrão é de ativos: a pessoa sai dela.
  await expect(dialogo).toHaveCount(0);
  await expect(page.getByText(NOME)).toHaveCount(0);
});

test("cancelar fecha o diálogo sem desativar ninguém", async ({ page }) => {
  // Reativa a pessoa para repetir o fluxo até o cancelar.
  djangoShell(
    `from django.contrib.auth import get_user_model\nget_user_model().objects.filter(pk=${userId}).update(ativo=True)`,
  );
  let apagou = false;
  page.on("request", (r) => {
    if (r.method() === "DELETE" && new URL(r.url()).pathname === `/api/v1/users/${userId}/`) apagou = true;
  });

  await page.goto("/admin/usuarios");
  await page.getByLabel("Buscar").fill("E2E-406");
  await page.getByTestId(`usuario-desativar-${userId}`).click();
  await expect(page.getByTestId("desativar-usuario-dialog")).toBeVisible();

  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByTestId("desativar-usuario-dialog")).toHaveCount(0);
  await expect(page.getByText(NOME)).toBeVisible();
  expect(apagou).toBe(false);
});
