import { expect, test, type Locator, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Log de Sincronização SCA (#157).
 *
 * Base de dados: `manage.py seed_demo` (#193). O bloco SCA cria três
 * dispositivos com faixas de sync fixas; para o log em si, o dev-seed-laranja
 * tem um push com dois erros pré-preenchidos:
 *
 *   { codigo: "PAYLOAD_INVALIDO",  mensagem: "CPF inválido no payload." }
 *   { codigo: "FORA_TERRITORIO",   mensagem: ""                          }
 *
 * A mensagem legível do primeiro é a âncora do teste de destaque/expansão.
 */
const PAGE_URL = "/sca/sync-events";
const MENSAGEM_ERRO_SEED = "CPF inválido no payload.";

function linhasVisiveis(page: Page): Locator {
  return page.locator('tr[data-testid^="sync-event-row-"]');
}

async function abrirLog(page: Page): Promise<void> {
  await page.goto(PAGE_URL);
  await expect(page.getByTestId("sca-sync-events-page")).toBeVisible();
  await expect(linhasVisiveis(page).first()).toBeVisible();
}

test.describe("SCA — Log de Sincronização", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("entrada com erro fica destacada e expande mostrando a mensagem detalhada", async ({
    page,
  }) => {
    await abrirLog(page);

    // Marca as linhas com erro no HTML (data-has-erros) — mais estável do que
    // depender só de classe visual.
    const linhaComErro = linhasVisiveis(page)
      .filter({ has: page.locator('[data-has-erros="true"]') })
      .first();

    // Filtro auxiliar quando o registro específico não fica na primeira
    // página; se cair no fallback, restringimos por dispositivo pra reduzir.
    if ((await linhaComErro.count()) === 0) {
      await page
        .getByRole("checkbox", { name: /Apenas eventos com erros/i })
        .check();
      await expect(linhasVisiveis(page).first()).toBeVisible();
    }

    const linha = linhasVisiveis(page)
      .filter({ has: page.locator('[data-has-erros="true"]') })
      .first();

    await expect(linha).toBeVisible();
    await expect(linha).toHaveAttribute("data-has-erros", "true");

    const idAttr = await linha.getAttribute("data-testid");
    const eventoId = idAttr?.replace("sync-event-row-", "");
    expect(eventoId).toBeTruthy();

    // Expande e valida que os detalhes vieram do endpoint /sync-events/{id}/.
    await linha.click();
    const detalhe = page.getByTestId(`sync-event-erros-${eventoId}`);
    await expect(detalhe).toBeVisible();
    await expect(detalhe).toContainText(MENSAGEM_ERRO_SEED);
    await expect(detalhe).toContainText("PAYLOAD_INVALIDO");
  });

  test("filtro por período restringe a listagem ao intervalo escolhido", async ({
    page,
  }) => {
    await abrirLog(page);

    // O topo da tabela é o evento mais recente (ordenação default do backend
    // é -iniciado_em). Usamos a data absoluta desse evento (title do <span>
    // com tempo relativo) como âncora — assim o teste independe de "hoje".
    const primeiraLinha = linhasVisiveis(page).first();
    const inicioColuna = primeiraLinha.locator("td").nth(1).locator("span");
    const titulo = (await inicioColuna.getAttribute("title")) ?? "";
    // formato "dd/MM/yyyy HH:mm" (absoluteDateTime, pt-BR)
    const match = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(titulo);
    expect(match, `data absoluta não encontrada em title="${titulo}"`).not
      .toBeNull();
    const dia = match![1];
    const mes = match![2];
    const ano = match![3];
    const isoDia = `${ano}-${mes}-${dia}`;

    const totalAntes = await linhasVisiveis(page).count();

    // Aplica "de = ate = dia do evento mais recente" → o range só cobre esse
    // dia específico. Como o seed cria eventos em faixas de "N dias atrás"
    // diferentes, a filtragem por 1 dia reduz o total.
    await page.getByLabel("De", { exact: true }).fill(isoDia);
    await page.getByLabel("Até", { exact: true }).fill(isoDia);

    // Espera o refetch — o skeleton overlay some quando a lista atualiza.
    await expect(linhasVisiveis(page).first()).toBeVisible();

    const totalDepois = await linhasVisiveis(page).count();
    expect(totalDepois).toBeLessThanOrEqual(totalAntes);
    expect(totalDepois).toBeGreaterThan(0);

    // Todos os eventos remanescentes devem ter a mesma data no title.
    for (let i = 0; i < totalDepois; i++) {
      const linha = linhasVisiveis(page).nth(i);
      const t = await linha
        .locator("td")
        .nth(1)
        .locator("span")
        .getAttribute("title");
      expect(t ?? "").toContain(`${dia}/${mes}/${ano}`);
    }
  });
});
