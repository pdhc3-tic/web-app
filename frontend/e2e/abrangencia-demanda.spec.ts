import { expect, test, type Page } from "@playwright/test";
import {
  criarAbrangenciaFixture,
  removerAbrangenciaFixture,
  type AbrangenciaFixture,
} from "./helpers/abrangenciaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #361 — Abrangência territorial da demanda (backend #352).
 *
 * A demanda segue o estado e o território de quem a cria, não os da
 * atividade. Contra o backend real: um ADT do RN monta e submete uma demanda
 * de uma atividade de PE; ela vai para a fila do Articulador de RN, com o
 * selo de atividade fora do território, e não aparece para a Articuladora de
 * PE.
 *
 * A primeira etapa do E2E da issue — achar a atividade de outro estado pela
 * busca — espera a rota do backend (pendencias-backend-sprint-12a.md, item 2);
 * a demanda nasce na fixture, pelo mesmo serviço do formulário.
 */

let fx: AbrangenciaFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarAbrangenciaFixture();
});

test.afterAll(() => {
  removerAbrangenciaFixture();
});

const linha = (page: Page) => page.getByTestId(`demanda-linha-${fx.demandaId}`);

test.describe("ADT do RN com atividade de PE", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("a busca de atividade não filtra por técnico", async ({ page }) => {
    await page.goto("/sgd/demandas/nova");
    const busca = page.waitForRequest(
      (req) => req.url().includes("/api/v1/sgp/atividades/?") && req.url().includes("q="),
    );
    await page.getByTestId("atividade-busca").fill("Oficina");
    const params = new URL((await busca).url()).searchParams;
    expect(params.has("tecnico_id")).toBe(false);
    expect(params.getAll("status")).toEqual(["planejado", "agendado"]);
  });

  test("a montagem mostra o território da demanda e avisa, sem bloquear, que a atividade é de outro estado", async ({
    page,
  }) => {
    await page.goto(`/sgd/demandas/${fx.demandaId}/editar`);
    await expect(page.getByTestId("montar-demanda")).toBeVisible();

    await expect(page.getByTestId("montar-abrangencia")).toHaveText(fx.abrangencia);
    const aviso = page.getByTestId("aviso-fora-do-territorio");
    await expect(aviso).toContainText("A atividade é em outro estado");
    await expect(aviso).toContainText(`Articulador de ${fx.estadoDemanda}`);

    const resposta = page.waitForResponse((r) => r.url().includes("/submeter/"));
    await page.getByTestId("demanda-submeter").click();
    expect((await resposta).status()).toBe(200);
    await page.waitForURL(`**/sgd/demandas?demanda=${fx.demandaId}`);

    const painel = page.getByTestId("demanda-painel");
    await expect(painel).toContainText("Submetida");
    await expect(painel.getByTestId("painel-abrangencia")).toHaveText(fx.abrangencia);
    await expect(painel.getByTestId("selo-fora-do-territorio")).toBeVisible();
  });
});

test.describe("Articulador de RN", () => {
  test.use({ storageState: storageStatePath("articuladorPB") });

  test("a demanda está na fila dele, com o selo e o território do solicitante", async ({ page }) => {
    await page.goto("/sgd/demandas");
    await expect(linha(page)).toBeVisible();
    await expect(linha(page).getByTestId("selo-fora-do-territorio")).toHaveText(
      "Atividade fora do território",
    );
    await expect(linha(page)).toContainText(fx.abrangencia);
  });
});

test.describe("Articuladora de PE", () => {
  test.use({ storageState: storageStatePath("articuladorPE") });

  test("não vê a demanda, embora a atividade seja do estado dela", async ({ page }) => {
    await page.goto("/sgd/demandas?visao=todas");
    await expect(page.getByTestId("demandas-tabela").or(page.getByText(/nenhuma demanda/i)).first()).toBeVisible();
    await expect(linha(page)).toHaveCount(0);
  });
});
