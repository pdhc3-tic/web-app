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
 * Atividades da demonstração, DESCOBERTAS por status no `beforeAll`.
 *
 * Ids fixos não sobrevivem: o `seed_demo` cria 45 atividades e os PKs dependem
 * de quantas vezes o banco já foi semeado. Num CI limpo vão de 1 a 45; numa
 * base local re-semeada passam de 100 — que é de onde vinham os ids antigos
 * (99, 91, 100, 105, 93), inexistentes no CI. Descobrir por status é o mesmo
 * padrão de `helpers/atividadeFixture.ts`, e falha cedo com mensagem clara se
 * o seed deixar de produzir algum dos estados.
 */
const ATIVIDADES = {
  planejado: 0,
  agendado: 0,
  adiada: 0,
  emAndamentoSemEvidencia: 0,
  terminal: 0,
};

const DESCOBRE_SCRIPT = `
import json
from django.db.models import Count
from apps.sgp.models import Activity


def primeira(status):
    a = Activity.objects.filter(status=status, ativo=True).order_by("pk").first()
    if a is None:
        raise RuntimeError(
            "seed_demo nao produziu atividade em '%s'. Rode "
            "manage.py seed_demo --reset." % status
        )
    return a.pk


# O aviso de evidencia so aparece quando nao ha foto nem documento: filtrar
# pelo status sozinho pegaria uma atividade ja com anexo, e o teste passaria
# a afirmar o contrario do que quer.
sem_evidencia = (
    Activity.objects.annotate(
        n_fotos=Count("fotos", distinct=True),
        n_docs=Count("documentos", distinct=True),
    )
    .filter(status="em_andamento", ativo=True, n_fotos=0, n_docs=0)
    .order_by("pk")
    .first()
)
if sem_evidencia is None:
    raise RuntimeError(
        "seed_demo nao produziu atividade em andamento sem evidencia. "
        "Rode manage.py seed_demo --reset."
    )

print("ATIVIDADES " + json.dumps({
    "planejado": primeira("planejado"),
    "agendado": primeira("agendado"),
    "adiada": primeira("adiada"),
    "emAndamentoSemEvidencia": sem_evidencia.pk,
    "terminal": primeira("concluido"),
}))
`;

function descobreAtividades(): Record<string, number> {
  const saida = execFileSync(
    "docker",
    [
      "compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c",
      DESCOBRE_SCRIPT,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith("ATIVIDADES "));
  if (!linha) throw new Error(`Não consegui descobrir as atividades:\n${saida}`);
  return JSON.parse(linha.slice("ATIVIDADES ".length)) as Record<string, number>;
}

test.beforeAll(() => {
  Object.assign(ATIVIDADES, descobreAtividades());
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

  /**
   * O atalho precisa ANEXAR, não apenas rolar até a galeria.
   *
   * A ficha é de leitura e a galeria nasce `readOnly`. O atalho fechava o modal
   * e rolava até esse mesmo bloco travado: nenhum controle de upload aparecia, e
   * o botão prometia uma ação que a tela não oferecia. Agora ele destrava a
   * galeria — e o "Concluir anexos" recarrega o detalhe, de onde o modal tira o
   * "falta evidência".
   */
  test("atalho de anexar destrava a galeria", async ({ page }) => {
    await abrirDialogo(page, ATIVIDADES.emAndamentoSemEvidencia);
    await escolherDestino(page, "Concluído");

    const evidencias = page.getByTestId("atividade-evidencias");
    // Antes do atalho: leitura pura.
    await expect(evidencias).toHaveAttribute("data-anexando", "nao");
    await expect(
      evidencias.getByRole("button", { name: /Adicionar fotos/i }),
    ).toHaveCount(0);

    await page.getByTestId("transicao-ir-evidencias").click();

    // O modal sai da frente e a galeria fica editável.
    await expect(page.getByTestId("transicao-dialog")).toHaveCount(0);
    await expect(evidencias).toHaveAttribute("data-anexando", "sim");
    await expect(page.getByTestId("atividade-anexo-aviso")).toBeVisible();
    await expect(
      evidencias.getByRole("button", { name: /Adicionar fotos/i }),
    ).toBeVisible();
    await expect(
      evidencias.getByRole("button", { name: /Adicionar documentos/i }),
    ).toBeVisible();

    // E o modo é reversível: a ficha volta a ser só leitura.
    await page.getByTestId("atividade-anexo-concluir").click();
    await expect(evidencias).toHaveAttribute("data-anexando", "nao");
    await expect(
      evidencias.getByRole("button", { name: /Adicionar fotos/i }),
    ).toHaveCount(0);
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
