import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Revogação de Acesso de Técnico (BE-15) — tela /admin/acessos-sca.
 *
 * Fonte de dados: `manage.py seed_demo`.
 *
 *   sca.verde@demo.pdhc.local     → acesso vigente, dispositivo dev-seed-verde.
 *                                   É o alvo do teste de revogação: nenhuma
 *                                   spec autentica com ele, então derrubá-lo
 *                                   por um instante não afeta a suíte.
 *   rodrigo.tavares@demo.pdhc.local → JÁ vem revogado (há 10 dias) e com o
 *                                   dispositivo dev-seed-revogado. É o único
 *                                   que nasce no estado "Revogado", e é por
 *                                   isso que o teste de reativação usa ele:
 *                                   chega ao diálogo sem revogar ninguém.
 *
 * A listagem consome `?com_dispositivo=true`, então só quem tem SyncDevice
 * aparece — daí o dispositivo do rodrigo existir no seed.
 */
const PAGE_URL = "/admin/acessos-sca";

const TECNICO_VIGENTE = "sca.verde@demo.pdhc.local";
const TECNICO_REVOGADO = "rodrigo.tavares@demo.pdhc.local";

function linhas(page: Page): Locator {
  return page.locator('tr[data-testid^="acesso-row-"]');
}

/** Abre a tela e filtra pelo e-mail, isolando uma única linha. */
async function abrirEBuscar(page: Page, email: string): Promise<Locator> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("acessos-sca-page")).toBeVisible();
  await page.getByTestId("acessos-busca").fill(email);
  const linha = linhas(page).filter({ hasText: email });
  await expect(linha).toHaveCount(1);
  return linha;
}

test.describe("Acessos SCA — Super Admin", () => {
  test.use({ storageState: storageStatePath("superAdmin") });

  test("revogar acesso reflete o status na listagem imediatamente", async ({
    page,
  }) => {
    const linha = await abrirEBuscar(page, TECNICO_VIGENTE);
    await expect(linha).toHaveAttribute("data-revogado", "false");

    try {
      await linha.getByRole("button", { name: "Revogar acesso" }).click();

      // O diálogo explica a consequência antes de confirmar.
      const dialogo = page.getByTestId("acesso-dialog-revogar");
      await expect(dialogo).toBeVisible();
      await expect(dialogo).toContainText(/apagará todos os dados locais/i);
      await expect(dialogo).toContainText(/próximo sync/i);

      await page.getByTestId("acesso-dialog-confirmar").click();

      // "Imediatamente" é o ponto do critério: a linha muda sem recarregar a
      // página e sem esperar o próximo sync do dispositivo.
      await expect(linha).toHaveAttribute("data-revogado", "true");
      await expect(linha).toContainText("Revogado");
      await expect(linha.getByRole("button", { name: "Reativar acesso" })).toBeVisible();

      const toast = page.getByTestId("toast");
      await expect(toast).toBeVisible();
      await expect(toast).toHaveAttribute("data-variant", "success");
    } finally {
      // O estado revogado sobrevive ao fim do teste e a suíte compartilha o
      // banco (workers: 1), então devolvemos o técnico ao estado do seed.
      const reativar = linha.getByRole("button", { name: "Reativar acesso" });
      if (await reativar.isVisible().catch(() => false)) {
        await reativar.click();
        await page.getByTestId("acesso-dialog-confirmar").click();
        await expect(linha).toHaveAttribute("data-revogado", "false");
      }
    }
  });

  test("reativação avisa que o técnico precisará de novo login", async ({
    page,
  }) => {
    const linha = await abrirEBuscar(page, TECNICO_REVOGADO);
    // Vem revogado do seed — a afordância de reativar existe para revogações
    // anteriores, que é justamente o que o critério pede.
    await expect(linha).toHaveAttribute("data-revogado", "true");

    await linha.getByRole("button", { name: "Reativar acesso" }).click();

    const dialogo = page.getByTestId("acesso-dialog-reativar");
    await expect(dialogo).toBeVisible();
    await expect(dialogo).toContainText(/novo login completo/i);
    await expect(dialogo).toContainText(/sessões anteriores foram invalidadas/i);

    // Cancela de propósito: o aviso é o que está sob teste, e sair sem
    // confirmar deixa o seed intacto para as próximas execuções.
    await page.getByTestId("acesso-dialog-cancelar").click();
    await expect(dialogo).toBeHidden();
    await expect(linha).toHaveAttribute("data-revogado", "true");
  });
});

test.describe("Acessos SCA — perfil sem permissão", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("usuário não Super Admin não acessa a rota", async ({ page }) => {
    await page.goto(PAGE_URL);

    // A tela não monta: o gate troca o conteúdo pelo <RestrictedAccess/> 403,
    // que é o padrão das demais telas de /admin (Usuários, Integrações) —
    // divergência deliberada do texto "redirecionado" no critério da issue.
    await expect(page.getByTestId("acessos-sca-page")).toHaveCount(0);
    // Escopado no <main>: o route announcer do Next também expõe role="alert"
    // (mesmo motivo do escopo em auth.setup.ts).
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Erro 403",
    );
    await expect(
      page.getByRole("heading", { name: "Conteúdo restrito" }),
    ).toBeVisible();

    // Sem afordância nenhuma para revogar.
    await expect(
      page.getByRole("button", { name: "Revogar acesso" }),
    ).toHaveCount(0);
  });

  test("o item de menu não aparece para quem não é Super Admin", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(
      page.getByRole("link", { name: "Acessos SCA" }),
    ).toHaveCount(0);
  });
});
