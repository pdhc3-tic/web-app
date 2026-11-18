import { expect, test, type Page } from "@playwright/test";
import {
  adicionarSolicitacao361,
  criarAbrangenciaFixture,
  PREFIXO_361,
  removerAbrangenciaFixture,
  type AbrangenciaFixture,
} from "./helpers/abrangenciaFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #361 — Abrangência territorial da demanda (backend #352 e PR #422).
 *
 * A demanda segue o estado e o território de quem a cria, não os da
 * atividade. Contra o backend real, pela tela: um ADT do RN acha pela busca
 * uma atividade de PE, vê antes de criar o território da demanda, quem vai
 * analisá-la e o aviso de atividade em outro estado, cria e submete. A
 * demanda vai para a fila do Articulador de RN, com o selo de atividade fora
 * do território, e não aparece para a Articuladora de PE.
 *
 * Só a solicitação (locação de veículo) entra pela fixture: o formulário de
 * veículo tem E2E próprio, e o foco aqui é a abrangência.
 */

let fx: AbrangenciaFixture;
let demandaId: number;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarAbrangenciaFixture();
});

test.afterAll(() => {
  removerAbrangenciaFixture();
});

const linha = (page: Page) => page.getByTestId(`demanda-linha-${demandaId}`);

test.describe("ADT do RN com atividade de PE", () => {
  test.use({ storageState: storageStatePath("adt") });

  test("acha a atividade de outro estado pela busca e vê a abrangência antes de criar", async ({
    page,
  }) => {
    await page.goto("/sgd/demandas/nova");

    const busca = page.waitForRequest(
      (req) => req.url().includes("/api/v1/sgd/atividades-elegiveis/?") && req.url().includes("q="),
    );
    await page.getByTestId("atividade-busca").fill("Feira agroecológica");
    const params = new URL((await busca).url()).searchParams;
    expect(params.has("tecnico_id")).toBe(false);
    expect(params.getAll("status")).toEqual(["planejado", "agendado"]);

    await page.getByRole("option", { name: new RegExp(fx.atividadeTitulo) }).click();
    await expect(page.getByTestId("demanda-contexto")).toContainText(`/${fx.estadoAtividade}`);

    await expect(page.getByTestId("previa-territorio")).toHaveText(fx.abrangencia);
    await expect(page.getByTestId("previa-articuladores")).toHaveText(fx.articuladores);
    const aviso = page.getByTestId("aviso-fora-do-territorio");
    await expect(aviso).toContainText(`A atividade é em ${fx.estadoAtividade}.`);
    await expect(aviso).toContainText(`Articulador de ${fx.estadoDemanda}`);

    await page.getByLabel("Título da demanda").fill(`${PREFIXO_361} Van para a feira em PE`);
    await page.getByTestId("nova-demanda-salvar").click();
    await page.waitForURL(/\/sgd\/demandas\/\d+\/editar$/);
    demandaId = Number(page.url().match(/\/sgd\/demandas\/(\d+)\/editar$/)![1]);

    // A demanda gravou a mesma abrangência que a prévia mostrou.
    await expect(page.getByTestId("montar-abrangencia")).toHaveText(fx.abrangencia);
    await expect(page.getByTestId("montar-articuladores")).toHaveText(fx.articuladores);
  });

  test("a montagem avisa, sem bloquear, e a submissão segue o território do solicitante", async ({
    page,
  }) => {
    adicionarSolicitacao361(demandaId);
    await page.goto(`/sgd/demandas/${demandaId}/editar`);
    await expect(page.getByTestId("montar-demanda")).toBeVisible();

    const aviso = page.getByTestId("aviso-fora-do-territorio");
    await expect(aviso).toContainText(`A atividade é em ${fx.estadoAtividade}.`);
    await expect(aviso).toContainText(`Articulador de ${fx.estadoDemanda}`);

    const resposta = page.waitForResponse((r) => r.url().includes("/submeter/"));
    await page.getByTestId("demanda-submeter").click();
    expect((await resposta).status()).toBe(200);
    await page.waitForURL(`**/sgd/demandas?demanda=${demandaId}`);

    const painel = page.getByTestId("demanda-painel");
    await expect(painel).toContainText("Submetida");
    await expect(painel.getByTestId("painel-abrangencia")).toHaveText(fx.abrangencia);
    await expect(painel.getByTestId("painel-articuladores")).toHaveText(fx.articuladores);
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
