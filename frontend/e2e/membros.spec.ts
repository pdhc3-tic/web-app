import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

/**
 * Aba "Membros" na ficha da UPF (#182).
 *
 * O cenário "com membros" sai do `seed_demo`, que cria um titular + cônjuge +
 * filhos em toda UPF. O cenário vazio NÃO tem como sair do seed: `UPF.titular`
 * é FK obrigatória para um `MembroFamilia` e esse membro aparece na própria
 * listagem — por isso o empty state é exercitado interceptando o GET da lista.
 *
 * A asserção do badge do Titular mora aqui, e não num teste de componente,
 * porque o projeto ainda não tem runner de componente (mesma pendência da
 * issue 133). Ao montar o runner, ela pode migrar para `MembrosTab.test.tsx`.
 */

/** Regex do GET da listagem — não pega o detalhe (`/membros/{id}/`). */
const LISTA_MEMBROS = /\/api\/v1\/sgp\/upfs\/\d+\/membros\/(\?|$)/;

async function abrirAbaMembros(page: Page, upfId: number): Promise<void> {
  await page.goto(`/sgp/upfs/${upfId}#membros`);
  // Sem isto a aba ainda pode estar sob o skeleton do fetch da própria UPF.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Membros" })).toBeVisible();
  await expect(page.getByTestId("membros-tab")).toBeVisible();
}

test.describe("SGP — Aba Membros na UPF", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("UPF com membros lista os integrantes com a idade calculada", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await abrirAbaMembros(page, upfId);

    const linhas = page.locator('tr[data-testid^="membro-row-"]');
    await expect(linhas.first()).toBeVisible();
    expect(await linhas.count()).toBeGreaterThan(0);

    // Idade calculada: 3ª coluna (Nome · Parentesco · Idade · …).
    await expect(linhas.first().locator("td").nth(2)).toHaveText(
      /^\d+ anos?$/,
    );

    // Badge do Titular: exatamente um por UPF, e na primeira linha — a tabela
    // ordena o titular no topo.
    const badges = page.getByTestId("membro-badge-titular");
    await expect(badges).toHaveCount(1);
    await expect(linhas.first().getByTestId("membro-badge-titular")).toBeVisible();

    // Campos sensíveis não podem aparecer na listagem resumida (regra FE-25).
    await expect(page.getByRole("columnheader", { name: "Saúde" })).toHaveCount(0);
    await expect(
      page.getByRole("columnheader", { name: "Cor/Raça" }),
    ).toHaveCount(0);

    // Clique na linha abre o painel do membro (detalhe → botão Editar).
    await linhas.first().click();
    await expect(page.getByTestId("membro-slideover")).toBeVisible();
    await expect(page.getByTestId("membro-slideover")).toHaveAttribute(
      "data-mode",
      "view",
    );
  });

  test("UPF sem membros exibe o estado vazio com CTA para cadastrar o Titular", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    await page.route(LISTA_MEMBROS, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });

    await abrirAbaMembros(page, upfId);

    await expect(
      page.getByText("Nenhum membro cadastrado ainda.", { exact: true }),
    ).toBeVisible();

    const cta = page.getByTestId("membros-adicionar-primeiro");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveText(/Adicionar primeiro membro/i);

    // O primeiro membro precisa ser o Titular — o formulário já abre assim.
    await cta.click();
    const painel = page.getByTestId("membro-slideover");
    await expect(painel).toBeVisible();
    await expect(painel).toHaveAttribute("data-mode", "create");
    await expect(painel.getByLabel("Parentesco")).toHaveValue("titular");
  });
});
