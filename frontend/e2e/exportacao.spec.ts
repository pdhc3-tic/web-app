import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { storageStatePath } from "./helpers/users";

/**
 * Exportação do Plano de Trabalho (FE-10).
 *
 * O arquivo é gerado inteiramente pelo backend em
 * `GET /api/v1/sgp/plano-trabalho/exportar/` (BE-9) — a tela só coleta os
 * filtros e entrega o binário ao browser. Por isso estes testes verificam o
 * caminho do download, não o conteúdo do dataset: as colunas e as agregações
 * têm cobertura própria em `backend/apps/sgp/tests/test_workplan_exports.py`.
 */

/** Cabeçalho do CSV — espelha EXPORT_COLUMNS do serviço de exportação. */
const CABECALHO_CSV = [
  "Meta",
  "Ação",
  "Tipo/Unidade",
  "Quantidade planejada",
  "Valor unitário",
  "Valor total",
  "Quantidade realizada",
  "Percentual realizado",
  "Status de execução",
  "Semáforo",
].join(",");

/**
 * `plano_trabalho_{data}.{ext}` — o padrão que a view monta.
 *
 * Em desenvolvimento o nome vem do fallback do cliente: o painel roda em :3000
 * e a API em :8080, e sem `CORS_EXPOSE_HEADERS` no Django o JS não lê o
 * `Content-Disposition`. O formato é o mesmo dos dois lados, então o teste
 * verifica o padrão — não o carimbo de tempo.
 */
const NOME_CSV = /^plano_trabalho_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.csv$/;
const NOME_XLSX = /^plano_trabalho_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.xlsx$/;

async function abrirModal(page: Page): Promise<void> {
  await page.goto("/sgp/painel");
  await expect(page.getByTestId("painel-page")).toBeVisible();
  await page.getByTestId("painel-exportar-btn").click();
  await expect(page.getByTestId("exportar-modal")).toBeVisible();
}

/** Escolhe uma opção num <Select> do design system pelo texto. */
async function escolher(page: Page, testId: string, texto: RegExp): Promise<void> {
  const campo = page.getByTestId(testId);
  await campo.locator('button[role="combobox"]').click();
  await campo.locator('li[role="option"]').filter({ hasText: texto }).click();
}

test.describe("Exportação do Plano de Trabalho — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("exportar em CSV filtrando uma Meta baixa um arquivo só com aquela Meta", async ({
    page,
  }) => {
    await abrirModal(page);

    await escolher(page, "exportar-formato", /^CSV/);
    await escolher(page, "exportar-meta", /^Meta 1 /);

    const download = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("exportar-confirmar").click(),
    ]).then(([d]) => d);

    expect(download.suggestedFilename()).toMatch(NOME_CSV);

    const caminho = await download.path();
    // O backend prefixa BOM para o Excel abrir os acentos corretamente.
    const conteudo = (await readFile(caminho, "utf8")).replace(/^﻿/, "");
    const linhas = conteudo.split(/\r?\n/).filter((l) => l !== "");

    expect(linhas[0]).toBe(CABECALHO_CSV);
    expect(linhas.length).toBeGreaterThan(1);

    // A coluna Meta sai como `{numero} - {titulo}`; vem entre aspas quando o
    // título tem vírgula. Todas as linhas precisam ser da Meta escolhida.
    for (const linha of linhas.slice(1)) {
      expect(linha).toMatch(/^"?1 - /);
    }

    await expect(page.getByTestId("exportar-modal")).toBeHidden();
  });

  test("exportar em Excel baixa um .xlsx válido", async ({ page }) => {
    await abrirModal(page);

    await escolher(page, "exportar-formato", /^Excel/);

    const download = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("exportar-confirmar").click(),
    ]).then(([d]) => d);

    expect(download.suggestedFilename()).toMatch(NOME_XLSX);

    const bytes = await readFile(await download.path());

    // Um .xlsx é um zip do OOXML: assinatura PK, o manifesto de tipos e ao
    // menos uma planilha. Basta isso para afirmar que o arquivo abre — validar
    // as células é trabalho do teste do backend.
    expect(bytes.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]));
    const bruto = bytes.toString("latin1");
    expect(bruto).toContain("[Content_Types].xml");
    expect(bruto).toContain("xl/worksheets/");
  });

  test("o modal mostra o estado de carregamento enquanto o backend gera o arquivo", async ({
    page,
  }) => {
    // A resposta fica presa até o teste soltar: é o único jeito de observar o
    // estado intermediário, que num backend saudável dura milissegundos.
    let liberar!: () => void;
    const liberacao = new Promise<void>((resolve) => {
      liberar = resolve;
    });

    await page.route(/\/plano-trabalho\/exportar\//, async (route) => {
      // O painel roda em :3000 e a API em :8080 — a resposta forjada precisa
      // trazer o CORS que o Django traria, inclusive no preflight.
      if (route.request().method() === "OPTIONS") {
        await route.fulfill({
          status: 204,
          headers: {
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET, OPTIONS",
            "access-control-allow-headers": "authorization, content-type",
          },
        });
        return;
      }

      await liberacao;
      await route.fulfill({
        status: 200,
        body: `${CABECALHO_CSV}\r\n`,
        headers: {
          "content-type": "text/csv; charset=utf-8",
          "content-disposition":
            'attachment; filename="plano_trabalho_2026-01-01_00-00-00.csv"',
          "access-control-allow-origin": "*",
          "access-control-expose-headers": "content-disposition",
        },
      });
    });

    await abrirModal(page);

    const download = page.waitForEvent("download");
    await page.getByTestId("exportar-confirmar").click();

    const carregando = page.getByTestId("exportar-carregando");
    await expect(carregando).toBeVisible();
    await expect(carregando).toContainText("Gerando o arquivo");
    // Enquanto gera, nada de fechar o modal por baixo da requisição.
    // Por testid, e não por papel: o backdrop do SlideOver é aria-hidden, então
    // getByRole não alcança nada dentro do painel.
    await expect(page.getByTestId("exportar-cancelar")).toBeDisabled();

    liberar();

    expect((await download).suggestedFilename()).toBe(
      "plano_trabalho_2026-01-01_00-00-00.csv",
    );
    await expect(carregando).toBeHidden();
    await expect(page.getByTestId("exportar-modal")).toBeHidden();
  });
});
