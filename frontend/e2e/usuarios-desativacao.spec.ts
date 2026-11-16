import { expect, test } from "@playwright/test";
import {
  NOME_406,
  criarDesativacaoFixture,
  lerEstadoDepois,
  reativarPessoa,
  removerDesativacaoFixture,
  type DesativacaoFixture,
} from "./helpers/desativacaoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #406 (AJ-FE-10) — Desativação de usuário com aviso de impacto, contra o
 * backend real (`GET /core/usuarios/{id}/impacto-desativacao/` e
 * `DELETE /users/{id}/`).
 *
 * A fixture cria uma técnica ADT com três demandas de Locação de veículo: uma
 * submetida de R$ 800 (com reserva), um rascunho de R$ 300 e uma autorizada de
 * R$ 500. O impacto esperado: cancelar as duas primeiras e liberar R$ 800; a
 * autorizada fica, e só ela continua comprometendo o limite e o pool.
 */

let fx: DesativacaoFixture;

test.describe.configure({ mode: "serial" });
test.use({ storageState: storageStatePath("superAdmin") });

test.beforeAll(() => {
  fx = criarDesativacaoFixture();
});

test.afterAll(() => {
  removerDesativacaoFixture();
});

async function abrirDialogo(page: import("@playwright/test").Page) {
  await page.goto("/admin/usuarios");
  await page.getByLabel("Buscar").fill("E2E-406");
  await expect(page.getByText(NOME_406)).toBeVisible();

  const impacto = page.waitForResponse((r) =>
    new URL(r.url()).pathname.endsWith(`/core/usuarios/${fx.userId}/impacto-desativacao/`),
  );
  await page.getByTestId(`usuario-desativar-${fx.userId}`).click();
  expect((await impacto).status()).toBe(200);
  const dialogo = page.getByTestId("desativar-usuario-dialog");
  await expect(dialogo).toContainText(NOME_406);
  return dialogo;
}

test("o diálogo lista as demandas e o saldo, e só desativa depois da confirmação explícita", async ({ page }) => {
  const antes = lerEstadoDepois();
  expect(antes.limiteComprometido).toBe("1300.00");

  const dialogo = await abrirDialogo(page);
  const { submetida, rascunho, autorizada } = fx.demandas;

  // As duas não autorizadas, com o saldo que cada uma reserva.
  await expect(dialogo).toContainText("Demandas que serão canceladas (2)");
  const linhaSubmetida = dialogo.getByTestId(`impacto-demanda-${submetida.id}`);
  await expect(linhaSubmetida).toContainText(submetida.titulo);
  await expect(linhaSubmetida).toContainText("R$ 800,00");
  const linhaRascunho = dialogo.getByTestId(`impacto-demanda-${rascunho.id}`);
  await expect(linhaRascunho).toContainText(rascunho.titulo);
  await expect(linhaRascunho).toContainText("R$ 0,00");
  await expect(dialogo.getByTestId(`impacto-demanda-${autorizada.id}`)).toHaveCount(0);

  await expect(dialogo.getByTestId(`impacto-rubrica-${fx.rubrica.id}`)).toContainText(fx.rubrica.nome);
  await expect(dialogo.getByTestId(`impacto-rubrica-${fx.rubrica.id}`)).toContainText("R$ 800,00");
  await expect(dialogo.getByTestId("impacto-total")).toHaveText("R$ 800,00");

  const confirmar = page.getByTestId("desativar-confirmar");
  await expect(confirmar).toBeDisabled();
  await dialogo.getByTestId("desativar-ciente").check();
  await expect(confirmar).toBeEnabled();

  const desativacao = page.waitForResponse(
    (r) => new URL(r.url()).pathname === `/api/v1/users/${fx.userId}/` && r.request().method() === "DELETE",
  );
  await confirmar.click();
  expect((await desativacao).status()).toBe(204);

  // A listagem padrão é de ativos: a pessoa sai dela.
  await expect(dialogo).toHaveCount(0);
  await expect(page.getByText(NOME_406)).toHaveCount(0);

  // O que o backend fez: o que o diálogo prometeu, e só isso.
  const depois = lerEstadoDepois();
  expect(depois.ativo).toBe(false);
  expect(depois.status).toEqual({
    [String(submetida.id)]: "cancelada",
    [String(rascunho.id)]: "cancelada",
    [String(autorizada.id)]: "autorizada",
  });
  expect(depois.limiteComprometido).toBe("500.00");
  expect(Number(antes.poolComprometido) - Number(depois.poolComprometido)).toBe(800);
});

test("sem demanda a cancelar, o diálogo diz isso; cancelar fecha sem desativar ninguém", async ({ page }) => {
  // A pessoa volta a ativa só com a demanda autorizada, que não é cancelada.
  reativarPessoa();
  let desativou = false;
  page.on("request", (r) => {
    if (r.method() === "DELETE" && new URL(r.url()).pathname === `/api/v1/users/${fx.userId}/`) desativou = true;
  });

  const dialogo = await abrirDialogo(page);
  await expect(dialogo.getByTestId("desativar-sem-impacto")).toContainText("Nenhuma demanda será cancelada");
  await expect(page.getByTestId("desativar-confirmar")).toBeDisabled();

  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(dialogo).toHaveCount(0);
  await expect(page.getByText(NOME_406)).toBeVisible();
  expect(desativou).toBe(false);
  expect(lerEstadoDepois().ativo).toBe(true);
});
