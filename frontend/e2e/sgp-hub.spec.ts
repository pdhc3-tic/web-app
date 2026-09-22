import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Hub do SGP (#276) — a página `/sgp` lista os submódulos do módulo.
 *
 * Ativos nesta branch: UPFs, Atividades, Calendário, Plano de Trabalho, Painel
 * e Orçamento. Técnicos, Produção e Relatórios aparecem como "Em breve" (sem
 * href) porque as páginas só existem no sprint 9d — deixar o href aqui levaria
 * a 404 até que o PR de lá mergeie.
 *
 * Estes testes travam esse contrato: nenhum card ativo pode virar link morto, e
 * os três "Em breve" precisam continuar como `aria-disabled` sem link enquanto
 * as páginas não estiverem no ar.
 */
const PAGE_URL = "/sgp";

const CARDS_ATIVOS: ReadonlyArray<{
  key: string;
  destino: RegExp;
}> = [
  { key: "upfs", destino: /\/sgp\/upfs\/?$/ },
  { key: "atividades", destino: /\/sgp\/atividades\/?$/ },
  { key: "calendario", destino: /\/sgp\/atividades\/calendario\/?$/ },
  { key: "plano", destino: /\/sgp\/metas\/?$/ },
  { key: "painel", destino: /\/sgp\/painel\/?$/ },
  { key: "orcamento", destino: /\/sgp\/orcamento\/?$/ },
];

const CARDS_EM_BREVE: readonly string[] = [
  "tecnicos",
  "producao",
  "relatorios",
];

async function abrirHub(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("sgp-hub-page")).toBeVisible();
}

test.describe("SGP — Hub", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("os nove submódulos do doc §1.1 são renderizados", async ({ page }) => {
    await abrirHub(page);

    for (const { key } of CARDS_ATIVOS) {
      await expect(page.getByTestId(`sgp-hub-card-${key}`)).toBeVisible();
    }
    for (const key of CARDS_EM_BREVE) {
      await expect(page.getByTestId(`sgp-hub-card-${key}`)).toBeVisible();
    }
  });

  for (const { key, destino } of CARDS_ATIVOS) {
    test(`card ativo "${key}" navega para a página correspondente`, async ({
      page,
    }) => {
      await abrirHub(page);

      // Cada card ativo é um <a>. O teste garante o contrato do #276: nenhum
      // href pode apontar para rota que ainda não existe (o motivo do bug
      // original em que Técnicos/Produção/Relatórios levavam a 404).
      const card = page.getByTestId(`sgp-hub-card-${key}`);
      await expect(card).toHaveAttribute("href", destino);

      await card.click();
      await page.waitForURL(destino);
    });
  }

  for (const key of CARDS_EM_BREVE) {
    test(`card "Em breve" (${key}) fica desabilitado e sem link`, async ({
      page,
    }) => {
      await abrirHub(page);

      const card = page.getByTestId(`sgp-hub-card-${key}`);
      await expect(card).toBeVisible();
      // Contrato do estado "Em breve" do SubmoduleCard: <div aria-disabled>
      // (não <a>), com badge "Em breve" e sem alvo de navegação.
      await expect(card).toHaveAttribute("aria-disabled", "true");
      await expect(card).not.toHaveAttribute("href", /.+/);
      await expect(card).toContainText("Em breve");
    });
  }
});
