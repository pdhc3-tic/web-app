import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Painel de Monitoramento de Dispositivos SCA (#156).
 *
 * Fonte de dados: `manage.py seed_demo` (issue #193) — cria três dispositivos
 * com sync em faixas fixas para exercer o semáforo:
 *
 *   dev-seed-verde     → sync há ~30 min (verde)
 *   dev-seed-laranja   → sync há 3 dias, com erros pendentes (laranja)
 *   dev-seed-vermelho  → sync há mais de `sca_sync_alerta_dias` (vermelho)
 *
 * Cada dispositivo vai para um técnico distinto (round-robin sobre territórios
 * ativos), então filtrar por um território devolve exatamente um dispositivo.
 */
const PAGE_URL = "/sca/dispositivos";

function tabela(page: Page): Locator {
  return page.locator('tr[data-testid^="dispositivo-row-"]');
}

async function abrirPainel(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("sca-dispositivos-page")).toBeVisible();
  // A primeira linha do seed é suficiente para saber que a listagem carregou —
  // asserção mais forte que "spinner sumiu" (que passa com tabela vazia).
  await expect(tabela(page).first()).toBeVisible();
}

test.describe("SCA — Painel de Dispositivos", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("dispositivo sem sincronizar há mais que o limiar mostra semáforo vermelho", async ({
    page,
  }) => {
    await abrirPainel(page);

    // dev-seed-vermelho vem do seed com `ultimo_push_em = agora - (limiar+2 dias)`
    // e é o único cuja última sync ultrapassa o limiar. O rótulo do badge é
    // "Sem sync" (statusLabel("vermelho") — lib/sca.ts).
    const linhaVermelha = tabela(page).filter({
      hasText: /Dev Seed Vermelho/i,
    });
    await expect(linhaVermelha).toHaveCount(1);
    await expect(
      linhaVermelha.getByLabel(/^Status:\s*Sem sync$/),
    ).toBeVisible();
  });

  test("filtro por território restringe a listagem só ao território escolhido", async ({
    page,
  }) => {
    await abrirPainel(page);

    // A contagem inicial serve de baseline: como o seed cria 3 dispositivos,
    // qualquer filtro específico devolve menos que isso. Se o backend passar a
    // criar mais dispositivos em outros territórios, o teste continua válido
    // (usa a linha do dev-seed-verde como âncora do território filtrado).
    const totalAntes = await tabela(page).count();
    expect(totalAntes).toBeGreaterThanOrEqual(3);

    // dev-seed-verde é o dispositivo do primeiro técnico do seed — pegamos o
    // nome do território exibido na coluna "Território" para escolher o filtro
    // sem hardcode do nome (que pode variar entre seeds).
    const linhaVerde = tabela(page).filter({ hasText: /Dev Seed Verde/i });
    const territorioAlvo = (
      await linhaVerde.locator("td").nth(2).innerText()
    ).trim();
    expect(territorioAlvo.length).toBeGreaterThan(0);

    // Abre o select de território (padrão do design system: button role
    // "combobox" + listbox com `li[role="option"]`).
    const selectTerritorio = page.getByRole("combobox", { name: "Território" });
    await selectTerritorio.click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: new RegExp(`^${escapeRegex(territorioAlvo)}$`) })
      .first()
      .click();

    // Depois do filtro, TODAS as linhas visíveis pertencem ao território
    // escolhido — a asserção mais forte que "só 1 dispositivo" (que quebraria
    // se o seed adicionar dispositivos no mesmo território depois).
    await expect(linhaVerde).toBeVisible();
    const totalDepois = await tabela(page).count();
    expect(totalDepois).toBeLessThan(totalAntes);

    for (let i = 0; i < totalDepois; i++) {
      const linha = tabela(page).nth(i);
      await expect(linha.locator("td").nth(2)).toContainText(territorioAlvo);
    }
  });

  test("clique em um dispositivo navega para o log de sincronização correspondente", async ({
    page,
  }) => {
    await abrirPainel(page);

    // A ordem default do painel joga o dev-seed-vermelho no topo (nulls_first
    // + sync mais antigo). Pegamos o id direto do data-testid pra montar a URL
    // esperada — resiste a mudanças no seed.
    const primeiraLinha = tabela(page).first();
    const idAttr = await primeiraLinha.getAttribute("data-testid");
    const deviceId = idAttr?.replace("dispositivo-row-", "");
    expect(deviceId).toBeTruthy();

    await primeiraLinha.click();
    await page.getByTestId("dispositivo-ver-log").click();
    await expect(page).toHaveURL(
      new RegExp(`/sca/sync-events\\?device=${deviceId}$`),
    );
    // A página do log carrega — a query string sobreviveu.
    await expect(page.getByTestId("sca-sync-events-page")).toBeVisible();
  });
});

/** Escapa metacaracteres de regex para poder usar strings do seed em regex. */
function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
