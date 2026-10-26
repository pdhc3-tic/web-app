import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Garantias de performance e carregamento do SGD (#323 · SGD-FE-12).
 *
 * O que a issue pede e este spec cobre:
 * 1. Skeleton visível durante o carregamento do painel por rubrica e da
 *    listagem de demandas (não um spinner centralizado).
 * 2. Cache do TanStack Query (#271): voltar à aba do SGD recém-visitada não
 *    refaz a mesma requisição dentro da janela de `staleTime`.
 *
 * O critério "paginação/scroll com volume alto (10.000 registros)" não cabe
 * no E2E, porque:
 *   - o seed_demo tem dezenas de registros, não milhares;
 *   - gerar 10k registros sintéticos no teste exigiria uma fixture específica
 *     e tempo real de execução; o backend precisa também paginar a listagem
 *     (pendencias-backend-sprint-10.md, item 13).
 * A cobertura desse NFR fica anotada em pendencias-backend-sprint-11.md.
 */

test.describe("SGD — carregamento sem salto de layout (#323)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("painel por rubrica mostra o skeleton antes dos dados reais", async ({ page }) => {
    // Segura a resposta do painel para o skeleton ficar visível tempo suficiente.
    await page.route("**/api/v1/sgd/painel/rubricas/*", async (route) => {
      await new Promise((r) => setTimeout(r, 300));
      await route.continue();
    });

    await page.goto("/sgd/execucao");
    const skeleton = page.getByTestId("painel-rubricas-skeleton");
    await expect(skeleton).toBeVisible();

    // A tabela real substitui o skeleton assim que a resposta chega.
    await expect(skeleton).toBeHidden({ timeout: 10_000 });
  });

  test("listagem de demandas mostra o skeleton antes da tabela real", async ({ page }) => {
    await page.route("**/api/v1/sgd/demandas/**", async (route) => {
      await new Promise((r) => setTimeout(r, 300));
      await route.continue();
    });

    await page.goto("/sgd/demandas?visao=todas");
    const skeleton = page.getByTestId("demandas-skeleton");
    await expect(skeleton).toBeVisible();
    await expect(skeleton).toBeHidden({ timeout: 10_000 });
  });

  test("voltar à aba do painel não refaz a mesma requisição dentro do staleTime", async ({
    page,
  }) => {
    let chamadas = 0;
    await page.route("**/api/v1/sgd/painel/rubricas/*", async (route) => {
      chamadas += 1;
      await route.continue();
    });

    await page.goto("/sgd/execucao");
    await expect(page.getByTestId("tab-rubricas")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    const chamadasApos1aCarga = chamadas;

    // Troca para a aba de atividades e volta — a aba de rubricas sai da tela,
    // mas a query continua montada por conta do `enabled=false` + cache.
    await page.getByTestId("tab-custo-atividades").click();
    await expect(page.getByTestId("tab-custo-atividades")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await page.getByTestId("tab-rubricas").click();
    await expect(page.getByTestId("tab-rubricas")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await page.waitForTimeout(300);

    // Nenhuma requisição extra deve sair enquanto o `staleTime` (30s) estiver
    // de pé: a #323 pede exatamente isso ("navegar entre abas do SGD e voltar
    // não dispara refetch desnecessário dos mesmos dados").
    expect(chamadas).toBe(chamadasApos1aCarga);
  });

  test("busca de atividade no filtro aplica debounce — uma requisição por texto estável", async ({
    page,
  }) => {
    let chamadas = 0;
    // O filtro de atividade usa /api/v1/sgp/atividades/?q=
    await page.route("**/api/v1/sgp/atividades/?*", async (route) => {
      chamadas += 1;
      await route.continue();
    });

    await page.goto("/sgd/execucao");
    const campo = page.getByTestId("filtro-atividade").locator("input");
    await campo.click();
    // Digita três teclas em sequência: só a última palavra "ativ" deve virar
    // requisição, por conta do debounce (300ms) do SearchSelect.
    await campo.pressSequentially("ativ", { delay: 50 });
    // Espera um pouco mais que o debounce para a última requisição sair.
    await page.waitForTimeout(500);

    // Antes do spec, a tela já pode ter feito outras chamadas a /atividades/
    // (sem `q`, por outros filtros). O que importa é não ter uma requisição
    // por tecla: digitamos 4 letras → no máximo uma chamada nova aqui.
    const chamadasDeBusca = chamadas;
    expect(chamadasDeBusca).toBeLessThanOrEqual(2);
  });
});
