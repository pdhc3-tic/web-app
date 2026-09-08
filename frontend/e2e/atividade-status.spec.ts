import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * Fluxo guiado de transição de status (Issue #234).
 *
 * A máquina de estados é do backend; estes testes cobrem o que a UI acrescenta
 * — oferecer só os destinos válidos e coletar o que cada um exige ANTES de
 * submeter, em vez de deixar o técnico descobrir a regra num 400.
 *
 * ─── Por que quase nenhum teste submete ─────────────────────────────────────
 *
 * Os critérios são sobre o que acontece antes do envio: opções oferecidas,
 * submissão bloqueada, aviso exibido. Submeter de verdade mudaria o status no
 * banco e o teste seguinte encontraria outra atividade. O único que precisa de
 * resposta do servidor é o do erro 400, e esse intercepta a rota.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..");

/**
 * Atividades da demonstração escolhidas por status e evidência.
 *
 * Ids fixos porque o `seed_demo` é determinístico (SEED fixo em seed_demo.py).
 * O `beforeAll` confere que cada uma está no status esperado e falha cedo, com
 * mensagem clara, se um re-seed tiver mudado a distribuição.
 */
const ATIVIDADES = {
  planejado: 99,
  agendado: 91,
  adiada: 100,
  emAndamentoSemEvidencia: 105,
  terminal: 93,
} as const;

const STATUS_ESPERADO: Record<number, string> = {
  99: "planejado",
  91: "agendado",
  100: "adiada",
  105: "em_andamento",
  93: "concluido",
};

function statusNoBanco(): Record<number, string> {
  const saida = execFileSync(
    "docker",
    [
      "compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c",
      `
import json
from apps.sgp.models import Activity
ids = [${Object.keys(STATUS_ESPERADO).join(", ")}]
print("STATUS " + json.dumps({
    a.pk: a.status for a in Activity.objects.filter(pk__in=ids)
}))
`,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
  const linha = saida.split("\n").map((l) => l.trim()).find((l) => l.startsWith("STATUS "));
  if (!linha) throw new Error(`Não consegui ler os status:\n${saida}`);
  const bruto = JSON.parse(linha.slice("STATUS ".length)) as Record<string, string>;
  return Object.fromEntries(
    Object.entries(bruto).map(([k, v]) => [Number(k), v]),
  );
}

test.beforeAll(() => {
  const atual = statusNoBanco();
  for (const [id, esperado] of Object.entries(STATUS_ESPERADO)) {
    const encontrado = atual[Number(id)];
    expect(
      encontrado,
      `Atividade ${id} deveria estar em "${esperado}" e está em "${encontrado}". ` +
        `Rode manage.py seed_demo --reset para restaurar a distribuição.`,
    ).toBe(esperado);
  }
});

/** Abre a ficha e o diálogo de transição. */
async function abrirDialogo(page: Page, id: number): Promise<void> {
  await page.goto(`/sgp/atividades/${id}/`);
  await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();
  await page.getByTestId("atividade-status-btn").click();
  await expect(page.getByTestId("transicao-dialog")).toBeVisible();
}

/**
 * Os rótulos oferecidos no seletor de destino.
 *
 * O <Select> do design system é um combobox custom (button + listbox), não um
 * <select> nativo — as opções só existem no DOM com a lista aberta.
 */
async function destinosOferecidos(page: Page): Promise<string[]> {
  const campo = page.getByTestId("transicao-destino");
  await campo.locator('button[role="combobox"]').click();
  const rotulos = await campo.locator('[role="option"]').allTextContents();
  await page.keyboard.press("Escape"); // fecha a lista, mantém o diálogo
  return rotulos;
}

/** Escolhe um destino no combobox. */
async function escolherDestino(page: Page, rotulo: string): Promise<void> {
  const campo = page.getByTestId("transicao-destino");
  await campo.locator('button[role="combobox"]').click();
  await campo
    .locator('[role="option"]')
    .filter({ hasText: new RegExp(`^${rotulo}$`) })
    .first()
    .click();
}

test.describe("Transição de status", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("oferece apenas as transições válidas", async ({ page }) => {
    await abrirDialogo(page, ATIVIDADES.planejado);

    const opcoes = (await destinosOferecidos(page)).join(" | ");

    // "planejado" → { agendado, cancelada } em STATUS_TRANSITIONS.
    expect(opcoes).toContain("Agendado");
    expect(opcoes).toContain("Cancelada");
    // O que NÃO pode aparecer é o que prova o filtro.
    expect(opcoes).not.toContain("Concluído");
    expect(opcoes).not.toContain("Em andamento");
    expect(opcoes).not.toContain("Adiada");
  });

  test("exige justificativa para Cancelada e bloqueia o envio sem texto", async ({
    page,
  }) => {
    await abrirDialogo(page, ATIVIDADES.agendado);

    await escolherDestino(page, "Cancelada");

    // O campo aparece por causa do destino escolhido.
    const justificativa = page.getByTestId("transicao-justificativa");
    await expect(justificativa).toBeVisible();

    // Submeter vazio não chama a API: a validação segura no cliente.
    await page.getByTestId("transicao-confirmar").click();
    await expect(justificativa).toContainText(/obrigatória/i);
    await expect(page.getByTestId("transicao-dialog")).toBeVisible();
  });

  test("exige nova data ao sair de Adiada", async ({ page }) => {
    await abrirDialogo(page, ATIVIDADES.adiada);

    await escolherDestino(page, "Agendado");

    const novaData = page.getByTestId("transicao-nova-data");
    await expect(novaData).toBeVisible();

    await page.getByTestId("transicao-confirmar").click();
    await expect(novaData).toContainText(/Informe a nova data/i);
    await expect(page.getByTestId("transicao-dialog")).toBeVisible();
  });

  test("avisa que falta evidência antes de tentar concluir", async ({ page }) => {
    await abrirDialogo(page, ATIVIDADES.emAndamentoSemEvidencia);

    await escolherDestino(page, "Concluído");

    // O aviso é anterior à submissão — é isso que o critério pede.
    const aviso = page.getByTestId("transicao-aviso-evidencia");
    await expect(aviso).toBeVisible();
    await expect(aviso).toContainText(/foto ou documento/i);

    // E o botão fica bloqueado, em vez de deixar o usuário colher um 400.
    await expect(page.getByTestId("transicao-confirmar")).toBeDisabled();

    // O atalho para anexar existe.
    await expect(page.getByTestId("transicao-ir-evidencias")).toBeVisible();
  });

  test("estado terminal não oferece transição", async ({ page }) => {
    await page.goto(`/sgp/atividades/${ATIVIDADES.terminal}/`);
    await expect(page.getByTestId("atividade-ficha-page")).toBeVisible();

    const botao = page.getByTestId("atividade-status-btn");
    // Desabilitado, e não ausente: some faria o usuário procurar por ele.
    await expect(botao).toBeVisible();
    await expect(botao).toBeDisabled();
    await expect(botao).toHaveAttribute("title", /estado final/i);
  });

  test("erro do servidor preserva o que foi preenchido", async ({ page }) => {
    await abrirDialogo(page, ATIVIDADES.agendado);

    // 400 forjado: provar a preservação não exige um erro real, e assim o
    // status no banco não muda.
    await page.route("**/api/v1/sgp/atividades/*/", async (route) => {
      if (route.request().method() !== "PATCH") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          justificativa: ["Justificativa muito curta para o registro."],
        }),
      });
    });

    await escolherDestino(page, "Cancelada");

    const texto = "Atividade cancelada por falta de quórum na comunidade.";
    await page.getByTestId("transicao-justificativa").locator("textarea").fill(texto);
    await page.getByTestId("transicao-confirmar").click();

    // O diálogo continua aberto, com a mensagem do servidor...
    await expect(page.getByTestId("transicao-dialog")).toBeVisible();
    await expect(page.getByTestId("transicao-justificativa")).toContainText(
      /muito curta/i,
    );
    // ...e o texto que o usuário escreveu continua lá.
    await expect(
      page.getByTestId("transicao-justificativa").locator("textarea"),
    ).toHaveValue(texto);
  });

  test("o diálogo prende o foco e fecha com Esc", async ({ page }) => {
    await abrirDialogo(page, ATIVIDADES.agendado);

    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toHaveAttribute("aria-modal", "true");
    // aria-labelledby aponta para o título — sem isso o leitor de tela anuncia
    // um diálogo sem nome.
    await expect(dialogo).toHaveAttribute("aria-labelledby", /.+/);

    // Percorre o painel inteiro e volta: com a armadilha ativa, o foco nunca
    // sai do diálogo, por mais Tabs que se dê.
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("Tab");
      const dentro = await dialogo.evaluate((el) =>
        el.contains(document.activeElement),
      );
      expect(dentro, `O foco escapou do diálogo no Tab nº ${i + 1}`).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("transicao-dialog")).toHaveCount(0);
  });
});
