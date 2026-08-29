import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Aba "Formulários" na ficha da UPF (#178) — testa integração da tabela +
 * modal de detalhe (#179) + empty state com CTA (stub, wire em #181).
 *
 * O seed_demo (#193) hoje NÃO cria FormResponse — portanto o cenário "com
 * respostas" fica marcado como `.fixme` até um seed cobrir a demo. O empty
 * state, por outro lado, é o comportamento esperado pra qualquer UPF do seed.
 */

function primeiroUpfId(): number {
  const linha = execFileSync(
    "docker",
    [
      "exec",
      "db",
      "psql",
      "-U",
      "postgres",
      "-d",
      "app_db",
      "-tAc",
      "select id from sgp_upf order by id limit 1;",
    ],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
  const id = Number(linha);
  expect(id, "seed não criou nenhuma UPF").toBeGreaterThan(0);
  return id;
}

test.describe("SGP — Aba Formulários na UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("UPF sem respostas exibe empty state com CTA de preenchimento", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}#formularios`);

    // Aguarda a ficha carregar — sem isto a aba pode ainda estar mostrando o
    // skeleton do fetch da UPF.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // A aba "Formulários" precisa aparecer no tablist (critério da issue).
    const abaFormularios = page.getByRole("tab", { name: "Formulários" });
    await expect(abaFormularios).toBeVisible();

    // #formularios já ativa a aba via useHashTab — o CTA do empty state deve
    // aparecer sem clique adicional.
    const cta = page.getByTestId("formularios-preencher-novo");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveText(/Preencher novo formulário/i);
  });

  test.fixme(
    "tabela ordena por data decrescente e clicar em linha abre o modal de detalhe",
    async ({ page }) => {
      // Depende de FormResponse no seed_demo — ainda não implementado. Assim
      // que o seed cobrir, remover o .fixme e ancorar por `respostas_json`
      // conhecido (ex.: um campo `atividade_principal`) na assertion do modal.
      const upfId = primeiroUpfId();
      await page.goto(`/sgp/upfs/${upfId}#formularios`);

      const linhas = page.locator('tr[data-testid^="formulario-row-"]');
      await expect(linhas.first()).toBeVisible();
      await linhas.first().click();

      const modal = page.getByTestId("resposta-formulario-slideover");
      await expect(modal).toBeVisible();
    },
  );
});
