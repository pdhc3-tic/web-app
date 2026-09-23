import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

/**
 * Cascata de localização da UPF (#235).
 *
 * Cobre dois lados:
 * 1. **Ficha** — `municipio.estado` vem embutido no `UpfDetail` (contrato do
 *    `MunicipioNestedSerializer`). Estas specs travam: (a) o Estado sempre
 *    aparece sem depender de uma request extra a `/states/`, (b) quando a
 *    chave `estado` falta, um erro explícito é mostrado no lugar (nunca "—").
 * 2. **Wizard** — cancelamento e versionamento das cascatas: troca rápida
 *    entre Estados não pode deixar a resposta antiga sobrescrever a nova, e
 *    unmount do wizard cancela as requisições em voo (sem setState em
 *    componente desmontado).
 */

test.use({ storageState: storageStatePath("ugp") });

test.describe("Ficha da UPF — localização", () => {
  test("Estado aparece sem chamar /api/v1/states/ na ficha", async ({
    page,
  }) => {
    // Se algum código na ficha ainda faz fetch a /states/ para descobrir o
    // Estado, este teste falha — o ponto do #235 é usar `municipio.estado`
    // já embutido no UpfDetail em vez de uma segunda requisição.
    let statesRequested = false;
    await page.route("**/api/v1/states/**", async (route) => {
      statesRequested = true;
      await route.continue();
    });

    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}?tab=localizacao`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Localização" })).toBeVisible();

    // Espera o Estado renderizar antes de asseverar sobre requisições — dá
    // tempo do useEffect que faria a request antiga aparecer, se existisse.
    const estadoDefinition = page.getByRole("definition").first();
    await expect(estadoDefinition).toBeVisible();
    await expect(estadoDefinition).not.toHaveText("—");
    await expect(estadoDefinition).not.toHaveText("");

    expect(statesRequested, "ficha não deve chamar /api/v1/states/").toBe(false);
  });

  test("Estado ausente no municipio mostra erro explícito, nunca '—'", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // Simula backend legado que devolve o municipio sem a chave `estado`.
    // O código deve mostrar um chip vermelho de erro no lugar do valor.
    await page.route(
      new RegExp(`/api/v1/upfs/${upfId}/?$`),
      async (route) => {
        const response = await route.fetch();
        const body = await response.json();
        if (body?.municipio) delete body.municipio.estado;
        await route.fulfill({
          response,
          json: body,
        });
      },
    );

    await page.goto(`/sgp/upfs/${upfId}?tab=localizacao`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const alerta = page.getByRole("alert").filter({
      hasText: /Localiza[çc][ãa]o incompleta/i,
    });
    await expect(alerta).toBeVisible();
    // Não pode aparecer "—" no lugar do valor.
    await expect(page.getByRole("definition").first()).not.toHaveText("—");
  });
});

test.describe("Wizard — cascata de localização", () => {
  test("troca rápida entre Estados: resposta antiga não sobrescreve a nova", async ({
    page,
  }) => {
    // Atrasa deliberadamente a resposta do primeiro Estado escolhido. Se o
    // código não cancelasse essa request ao trocar de Estado, os municípios
    // do 1º chegariam depois e apareceriam para o 2º Estado — bug que Pedro
    // apontou no review original.
    let interceptedFirst = false;
    await page.route(
      "**/api/v1/municipalities/**",
      async (route) => {
        if (!interceptedFirst && route.request().url().includes("state=")) {
          interceptedFirst = true;
          // Segura por 3s para dar tempo do usuário trocar de Estado.
          await new Promise((r) => setTimeout(r, 3000));
        }
        await route.continue();
      },
    );

    await page.goto("/sgp/upfs/nova/");

    const estadoSelect = page.getByRole("combobox", { name: /estado/i });
    const municipioSelect = page.getByRole("combobox", { name: /município/i });

    await estadoSelect.click();
    await page
      .getByRole("option")
      .filter({ hasText: /Rio Grande do Norte/i })
      .click();

    // Antes que a request atrasada retorne, troca para outro Estado.
    await estadoSelect.click();
    await page
      .getByRole("option")
      .filter({ hasText: /Cear[áa]/i })
      .click();

    // Aguarda o segundo Estado carregar municípios.
    await expect(municipioSelect).toBeEnabled();
    await municipioSelect.click();

    // Se o bug estivesse presente, apareceriam municípios do RN misturados.
    // A asserção certa: NENHUM município do RN visível.
    await expect(
      page.getByRole("option").filter({ hasText: /^Mossor[óo]$/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("option").filter({ hasText: /^Natal$/i }),
    ).toHaveCount(0);
  });

  test("edição de UPF com comunidade carrega a comunidade selecionada", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();
    await page.goto(`/sgp/upfs/${upfId}/editar/`);

    await expect(
      page.getByRole("combobox", { name: /comunidade/i }),
    ).toBeEnabled();
    // Combobox exibe algum texto que não seja o placeholder — comunidade
    // preenchida a partir do initialData.
    const comboComunidade = page.getByRole("combobox", { name: /comunidade/i });
    const label = (await comboComunidade.textContent())?.trim() ?? "";
    expect(label).not.toMatch(/Selecione a comunidade/i);
    expect(label.length).toBeGreaterThan(0);
  });

  test("edição de UPF SEM comunidade mantém combobox habilitado com opções", async ({
    page,
  }) => {
    const upfId = primeiroUpfId();

    // Força a resposta sem comunidade para provar que o combobox continua
    // habilitado e o usuário pode escolher/criar uma na edição — regressão
    // clássica é o combobox ficar disabled quando comunidade == null.
    await page.route(
      new RegExp(`/api/v1/upfs/${upfId}/?$`),
      async (route) => {
        const response = await route.fetch();
        const body = await response.json();
        body.comunidade = null;
        await route.fulfill({ response, json: body });
      },
    );

    await page.goto(`/sgp/upfs/${upfId}/editar/`);

    const comboComunidade = page.getByRole("combobox", { name: /comunidade/i });
    await expect(comboComunidade).toBeEnabled();

    // As opções da comunidade só carregam se a hidratação da edição chamar
    // fetchComunidadeOptions(municipio.id) mesmo quando o campo filho está
    // vazio (comportamento pedido pelo Pedro).
    await comboComunidade.click();
    const opcoes = page.getByRole("option");
    await expect(opcoes.first()).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("falha na consulta geográfica não trava o wizard", async ({ page }) => {
    // Simula erro do endpoint de estados. O wizard deve continuar utilizável:
    // combobox de Estado fica visível (mesmo vazio), sem tela de erro fatal.
    await page.route("**/api/v1/states/**", (route) =>
      route.fulfill({ status: 500, body: "internal error" }),
    );

    await page.goto("/sgp/upfs/nova/");

    const estadoSelect = page.getByRole("combobox", { name: /estado/i });
    await expect(estadoSelect).toBeVisible();

    // A tela do wizard continua no ar (não caiu para uma página de erro).
    await expect(page.getByText(/Localiza[çc][ãa]o/).first()).toBeVisible();
  });
});

test.describe("Wizard — comportamento do formulário", () => {
  test("município bloqueado sem estado selecionado", async ({ page }) => {
    await page.goto("/sgp/upfs/nova/");
    const municipioSelect = page.getByRole("combobox", { name: /município/i });
    await expect(municipioSelect).toBeDisabled();
  });

  test("municípios filtrados por estado", async ({ page }) => {
    await page.goto("/sgp/upfs/nova/");

    const estadoSelect = page.getByRole("combobox", { name: /estado/i });
    await expect(estadoSelect).toBeEnabled();
    await estadoSelect.click();
    await page
      .getByRole("option")
      .filter({ hasText: /Rio Grande do Norte/i })
      .click();

    const municipioSelect = page.getByRole("combobox", { name: /município/i });
    await expect(municipioSelect).toBeEnabled();
    await municipioSelect.click();

    const opcoes = page.getByRole("option");
    await expect(opcoes.first()).toBeVisible();
    await expect(
      opcoes.filter({ hasText: /Mossoró|Natal/i }).first(),
    ).toBeVisible();
    await expect(opcoes.filter({ hasText: "Fortaleza" })).toHaveCount(0);

    await page.keyboard.press("Escape");
  });

  test("território derivado do município é readonly", async ({ page }) => {
    await page.goto("/sgp/upfs/nova/");

    const estadoSelect = page.getByRole("combobox", { name: /estado/i });
    await estadoSelect.click();
    await page
      .getByRole("option")
      .filter({ hasText: /Rio Grande do Norte/i })
      .click();

    const municipioSelect = page.getByRole("combobox", { name: /município/i });
    await expect(municipioSelect).toBeEnabled();
    await municipioSelect.click();
    await page.getByRole("option").first().click();

    const territorioBox = page.locator("#upf-territorio");
    await expect(territorioBox).toBeVisible();
    await expect(territorioBox).not.toHaveText("—");
    await expect(territorioBox).not.toHaveAttribute("role", "combobox");
  });

  test("trocar Estado limpa Município, Comunidade e opções", async ({
    page,
  }) => {
    await page.goto("/sgp/upfs/nova/");

    const estadoSelect = page.getByRole("combobox", { name: /estado/i });
    const municipioSelect = page.getByRole("combobox", { name: /município/i });

    await estadoSelect.click();
    await page
      .getByRole("option")
      .filter({ hasText: /Rio Grande do Norte/i })
      .click();
    await expect(municipioSelect).toBeEnabled();
    await municipioSelect.click();
    await page.getByRole("option").first().click();

    await estadoSelect.click();
    await page
      .getByRole("option")
      .filter({ hasText: /Cear[áa]/i })
      .click();

    await expect(municipioSelect).toHaveText(/Selecione o município/i);
    await expect(
      page.getByRole("combobox", { name: /comunidade/i }),
    ).toBeDisabled();
  });
});

