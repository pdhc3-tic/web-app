import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Hub do SGP (#276) — a página `/sgp` lista os submódulos do módulo.
 *
 * Os nove submódulos estão no ar. Estes testes travam o contrato de que nenhum
 * card vira link morto. Relatórios só aparece para quem pode exportar
 * (relatorios.spec.ts cobre a FGD, que não vê o card).
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
  { key: "tecnicos", destino: /\/sgp\/tecnicos\/?$/ },
  { key: "producao", destino: /\/sgp\/producao\/?$/ },
  { key: "relatorios", destino: /\/sgp\/relatorios\/?$/ },
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
});
