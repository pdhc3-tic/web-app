import {
  expect,
  test,
  type Locator,
  type Page,
  type Response,
} from "@playwright/test";
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
const SYNC_EVENTS_API = "/api/v1/sca/sync-events";
const MENSAGEM_ERRO_SEED = "CPF inválido no payload.";

function linhasVisiveis(page: Page): Locator {
  return page.locator('tr[data-testid^="sync-event-row-"]');
}

/**
 * Aguarda uma resposta GET da listagem que satisfaça `predicate` sobre a
 * querystring. Chame ANTES da ação que dispara o refetch (Promise já pendurada
 * para não perder responses rápidos). Assim o teste não corre atrás da UI —
 * espera pelo tráfego HTTP correspondente ao novo filtro.
 */
function esperarRefetch(
  page: Page,
  predicate: (params: URLSearchParams) => boolean,
): Promise<Response> {
  return page.waitForResponse((response) => {
    const url = new URL(response.url());
    if (!url.pathname.includes(SYNC_EVENTS_API)) return false;
    if (response.request().method() !== "GET") return false;
    if (response.status() !== 200) return false;
    return predicate(url.searchParams);
  });
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
    // página; se cair no fallback, restringimos por "com erro" pra reduzir.
    if ((await linhaComErro.count()) === 0) {
      // Pendura o listener ANTES do click — evita a race em que o refetch
      // é rápido demais e o test.expect passa lendo a lista antiga.
      const refetch = esperarRefetch(
        page,
        (params) => params.get("com_erro") === "true",
      );
      await page
        .getByRole("checkbox", { name: /Apenas eventos com erros/i })
        .check();
      await refetch;
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
    // é -iniciado_em). Usamos a data absoluta desse evento como âncora — assim
    // o teste independe de "hoje".
    const primeiraLinha = linhasVisiveis(page).first();
    const texto = await primeiraLinha
      .getByTestId("sync-event-inicio")
      .innerText();
    // formato "dd/MM/yyyy HH:mm" (absoluteDateTime, pt-BR)
    const match = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(texto.trim());
    expect(match, `data absoluta não encontrada em "${texto}"`).not.toBeNull();
    const dia = match![1];
    const mes = match![2];
    const ano = match![3];
    const isoDia = `${ano}-${mes}-${dia}`;

    const totalAntes = await linhasVisiveis(page).count();

    // Aplica "de = ate = dia do evento mais recente" → o range só cobre esse
    // dia específico. Como o seed cria eventos em faixas de "N dias atrás"
    // diferentes, a filtragem por 1 dia reduz o total.
    //
    // Pendura o listener ANTES dos fills — precisa esperar o request com
    // AMBOS os filtros aplicados (o fill de "De" sozinho já dispararia um
    // request intermediário, sem `iniciado_em_lte`).
    const refetch = esperarRefetch(
      page,
      (params) =>
        params.has("iniciado_em_gte") && params.has("iniciado_em_lte"),
    );
    await page.getByLabel("De", { exact: true }).fill(isoDia);
    await page.getByLabel("Até", { exact: true }).fill(isoDia);
    await refetch;

    // Sanidade visual — depois do refetch, alguma linha do novo conjunto
    // já está pintada (o `data-testid=sync-event-row-*` só vira com dados).
    await expect(linhasVisiveis(page).first()).toBeVisible();

    const totalDepois = await linhasVisiveis(page).count();
    expect(totalDepois).toBeLessThanOrEqual(totalAntes);
    expect(totalDepois).toBeGreaterThan(0);

    // Todos os eventos remanescentes devem exibir a mesma data no início.
    for (let i = 0; i < totalDepois; i++) {
      const t = await linhasVisiveis(page)
        .nth(i)
        .getByTestId("sync-event-inicio")
        .innerText();
      expect(t).toContain(`${dia}/${mes}/${ano}`);
    }
  });

  test("colunas Início e Fim mostram data e hora, com travessão em evento sem término", async ({
    page,
  }) => {
    await abrirLog(page);

    // Cabeçalhos na ordem esperada — "Fim" entre "Início" e "Duração".
    const cabecalhos = page.locator("thead th");
    await expect(cabecalhos.nth(1)).toHaveText("Início");
    await expect(cabecalhos.nth(2)).toHaveText("Fim");
    await expect(cabecalhos.nth(3)).toHaveText("Duração");

    const ABSOLUTA = /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/;

    const total = await linhasVisiveis(page).count();
    expect(total).toBeGreaterThan(0);

    for (let i = 0; i < total; i++) {
      const linha = linhasVisiveis(page).nth(i);

      // Início sempre com data e hora — não só o tempo relativo.
      const inicio = (
        await linha.getByTestId("sync-event-inicio").innerText()
      ).trim();
      expect(inicio, `linha ${i}: início "${inicio}"`).toMatch(ABSOLUTA);

      // Fim: ou data válida, ou o travessão do evento ainda em andamento —
      // nunca "Invalid Date" / "NaN".
      const fim = (await linha.getByTestId("sync-event-fim").innerText()).trim();
      expect(fim, `linha ${i}: fim "${fim}"`).toMatch(
        new RegExp(`(${ABSOLUTA.source})|^—$`),
      );
    }
  });

  test("filtro por técnico vai para a URL, sobrevive ao reload e envia user=<id>", async ({
    page,
  }) => {
    await abrirLog(page);

    // Âncora: o técnico do primeiro evento listado. Escolher pela tabela (e
    // não pela primeira opção do select) garante que o recorte tem pelo menos
    // um resultado — não existe "técnico com dispositivo mas sem evento" aqui.
    const nomeTecnico = (
      await linhasVisiveis(page)
        .first()
        .getByTestId("sync-event-tecnico")
        .locator("span")
        .first()
        .innerText()
    ).trim();
    expect(nomeTecnico.length).toBeGreaterThan(0);

    const select = page.getByLabel("Técnico", { exact: true });
    await expect(select).toBeVisible();
    await select.click();

    // Listener pendurado ANTES do clique: a request precisa carregar `user`.
    const refetch = esperarRefetch(page, (params) => params.has("user"));
    await page.getByRole("option", { name: nomeTecnico, exact: true }).click();
    const resposta = await refetch;
    await expect(linhasVisiveis(page).first()).toBeVisible();

    // O id enviado à API é o mesmo que foi para a querystring da página.
    const userEnviado = new URL(resposta.url()).searchParams.get("user");
    expect(userEnviado).toMatch(/^\d+$/);
    await expect(page).toHaveURL(new RegExp(`[?&]tecnico=${userEnviado}(&|$)`));

    // Todos os eventos listados são do técnico escolhido.
    const total = await linhasVisiveis(page).count();
    expect(total).toBeGreaterThan(0);
    for (let i = 0; i < total; i++) {
      await expect(
        linhasVisiveis(page).nth(i).getByTestId("sync-event-tecnico"),
      ).toContainText(nomeTecnico);
    }

    // Sobrevive ao reload: o filtro volta da URL, não do estado em memória.
    const aposReload = esperarRefetch(
      page,
      (params) => params.get("user") === userEnviado,
    );
    await page.reload();
    await aposReload;
    await expect(page.getByLabel("Técnico", { exact: true })).toContainText(
      nomeTecnico,
    );
  });

  test("técnico combina com período e dispositivo na mesma query", async ({
    page,
  }) => {
    await abrirLog(page);

    const primeira = linhasVisiveis(page).first();
    const nomeTecnico = (
      await primeira.getByTestId("sync-event-tecnico").locator("span").first()
        .innerText()
    ).trim();

    await page.getByLabel("Técnico", { exact: true }).click();
    const refetchTecnico = esperarRefetch(page, (p) => p.has("user"));
    await page.getByRole("option", { name: nomeTecnico, exact: true }).click();
    await refetchTecnico;

    // Período por cima do técnico: a query precisa levar os dois, não trocar
    // um pelo outro.
    const hoje = new Date().toISOString().slice(0, 10);
    const refetchCombinado = esperarRefetch(
      page,
      (p) =>
        p.has("user") && p.has("iniciado_em_gte") && p.has("iniciado_em_lte"),
    );
    await page.getByLabel("De", { exact: true }).fill("2020-01-01");
    await page.getByLabel("Até", { exact: true }).fill(hoje);
    await refetchCombinado;

    // E a URL reflete o conjunto inteiro, não só o último filtro mexido.
    await expect(page).toHaveURL(/[?&]tecnico=\d+/);
    await expect(page).toHaveURL(/[?&]de=2020-01-01/);
    await expect(page).toHaveURL(new RegExp(`[?&]ate=${hoje}`));
  });
});
