import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Grade do calendário de atividades (`/sgp/atividades/calendario`).
 *
 * ─── Por que esta spec existe ───────────────────────────────────────────────
 *
 * A rota não tinha nenhuma cobertura E2E — `google-calendar.spec.ts` testa o
 * painel de configuração da integração, não a grade. Foi por isso que passou um
 * `<button>` de pílula de evento DENTRO do `<button>` da célula do dia: HTML
 * inválido, que o React derruba na hidratação com
 * "<button> cannot be a descendant of <button>".
 *
 * O erro só aparecia no console, sem quebrar nada visível, então nenhum teste
 * de comportamento o pegaria. Daí o primeiro teste olhar o console; os outros
 * cobrem as duas afordâncias que a correção reorganizou — a célula virou uma
 * `<div>` com o botão de "criar" como camada de fundo, irmã das pílulas.
 */

/** Mês fixo: a grade é a mesma em qualquer data, e uma âncora fixa dispensa
 *  depender de o seed ter atividade "hoje". */
const ANCORA = "2026-09-09";
const ROTA = `/sgp/atividades/calendario?data=${ANCORA}`;

/**
 * Erros de console que o teste ignora.
 *
 * A grade carrega opções de filtro de endpoints que respondem 403 a perfis não
 * globais (`/api/v1/users/`, por exemplo, é `IsSuperAdmin`) — o front trata e
 * degrada, mas o Chrome registra o 4xx como erro de rede. Nada disso é
 * hidratação, que é o que esta spec vigia.
 */
const RUIDO = [
  /Failed to load resource/i,
  /the server responded with a status of 4\d\d/i,
  /favicon/i,
];

function coletarErros(page: Page): string[] {
  const erros: string[] = [];
  const registrar = (m: ConsoleMessage) => {
    if (m.type() !== "error" && m.type() !== "warning") return;
    const texto = m.text();
    if (RUIDO.some((r) => r.test(texto))) return;
    erros.push(`[${m.type()}] ${texto}`);
  };
  page.on("console", registrar);
  page.on("pageerror", (e) => erros.push(`[pageerror] ${e.message}`));
  return erros;
}

/** Abre a grade do mês e espera a carga terminar. */
async function abrirGradeDoMes(page: Page): Promise<void> {
  await page.goto(ROTA);
  await expect(page.getByTestId("calendario-grade-mes")).toBeVisible();

  // A grade vai de `startOfWeek(início do mês)` a `endOfWeek(fim do mês)`, então
  // são 4 a 6 semanas conforme o mês cai — setembro/2026 dá 35 células (30/ago a
  // 03/out), não 42. Esperar a célula da âncora é o que garante que o render
  // terminou, sem depender do número de semanas.
  await expect(page.getByTestId(`calendario-dia-${ANCORA}`)).toBeVisible();

  const celulas = await page
    .locator('[data-testid^="calendario-dia-"]')
    .count();
  // Semanas completas: a grade nunca corta um domingo ou um sábado no meio.
  expect(celulas % 7, `grade com ${celulas} células`).toBe(0);
  expect(celulas).toBeGreaterThanOrEqual(28);
  expect(celulas).toBeLessThanOrEqual(42);
}

/**
 * Data (chave `yyyy-MM-dd`) de uma célula SEM nenhuma pílula de evento.
 *
 * O botão de "criar neste dia" cobre a célula inteira, e as pílulas ficam por
 * cima dele — é assim que deve ser: quem clica numa pílula quer o evento, não
 * um formulário novo. Então o teste do "criar" precisa de um dia vazio; clicar
 * no centro de um dia cheio acerta a pílula, e é isso que o navegador faz.
 */
async function diaSemEvento(page: Page): Promise<string> {
  const celulas = page.locator('[data-testid^="calendario-dia-"]');
  const total = await celulas.count();

  for (let i = 0; i < total; i++) {
    const celula = celulas.nth(i);
    const pilulas = celula.locator('[data-testid^="calendario-evento-"]');
    if ((await pilulas.count()) === 0) {
      const testid = await celula.getAttribute("data-testid");
      return testid!.replace("calendario-dia-", "");
    }
  }
  throw new Error(
    "Todas as células do mês têm evento — o teste do 'criar' precisa de uma vazia",
  );
}

test.describe("Calendário — grade do mês", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("hidrata sem <button> dentro de <button>", async ({ page }) => {
    const erros = coletarErros(page);

    await abrirGradeDoMes(page);
    // A hidratação acontece depois do primeiro paint; a espera pela célula da
    // âncora já passou por ela, mas o aviso pode chegar no mesmo tick.
    await expect(page.getByTestId("calendario-grade-mes")).toBeVisible();

    const aninhamento = erros.filter((e) =>
      /cannot be a descendant of|cannot contain a nested|hydrat/i.test(e),
    );
    expect(
      aninhamento,
      `Erros de hidratação no console:\n${aninhamento.join("\n")}`,
    ).toEqual([]);
  });

  test("clicar no vazio da célula leva ao formulário com a data preenchida", async ({
    page,
  }) => {
    await abrirGradeDoMes(page);

    // Dia vazio: é onde o fundo da célula está exposto. O clique vai pelo
    // testid, e não por coordenada — é o que prova que o botão de "criar"
    // existe como elemento próprio, e não como a célula inteira.
    const dia = await diaSemEvento(page);
    await page.getByTestId(`calendario-criar-${dia}`).click();

    await expect(page).toHaveURL(
      new RegExp(`/sgp/atividades/nova/?\\?.*data_inicio=${dia}`),
    );
    await expect(page).toHaveURL(new RegExp(`data_fim=${dia}`));
  });

  test("clicar numa pílula abre o detalhe, e não o formulário", async ({
    page,
  }) => {
    await abrirGradeDoMes(page);

    const pilulas = page.locator('[data-testid^="calendario-evento-"]');
    if ((await pilulas.count()) === 0) {
      test.skip(
        true,
        `Nenhuma atividade na grade de ${ANCORA}: rode manage.py seed_demo`,
      );
    }

    const titulo = await pilulas.first().locator("span").last().innerText();
    await pilulas.first().click();

    // O clique na pílula NÃO pode disparar o "criar": era o risco de a célula
    // inteira ser clicável, e continua sendo o risco se as camadas de
    // pointer-events se invertessem.
    await expect(page).toHaveURL(new RegExp("/sgp/atividades/calendario"));

    const detalhe = page.getByRole("dialog");
    await expect(detalhe).toBeVisible();
    await expect(detalhe).toContainText(titulo.trim());
  });

  test("Esc fecha o detalhe e a grade continua operável", async ({ page }) => {
    await abrirGradeDoMes(page);

    const pilulas = page.locator('[data-testid^="calendario-evento-"]');
    if ((await pilulas.count()) === 0) {
      test.skip(true, `Nenhuma atividade na grade de ${ANCORA}`);
    }
    const dia = await diaSemEvento(page);

    await pilulas.first().click();
    await expect(page.getByRole("dialog")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // A grade segue operável depois de o SlideOver devolver o foco: o botão de
    // fundo continua recebendo clique, e não ficou coberto por resíduo do
    // overlay do diálogo.
    await page.getByTestId(`calendario-criar-${dia}`).click();
    // Barra final opcional: o `router.push` manda `/nova/?...` e o Next
    // normaliza para `/nova?...`.
    await expect(page).toHaveURL(/\/sgp\/atividades\/nova\/?\?/);
  });
});
