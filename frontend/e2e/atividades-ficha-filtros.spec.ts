import { expect, test, type Page, type Response } from "@playwright/test";
import { descobrirAtividadesDaFicha, type FichaAtividadeFixture } from "./helpers/fichaAtividadeFixture";
import { storageStatePath } from "./helpers/users";

/**
 * #464 (SGP-RF08, RF12, RF15) contra o backend real, só leitura:
 * - filtros de Meta, Submeta e Indicador na lista de Atividades, com as
 *   contagens conferidas no banco;
 * - ficha sem coordenadas, parceiros, participantes e resultados mostrando o
 *   "—" e os avisos, e as datas de início e fim com a hora;
 * - aba Demandas com rubricas e valores estimado, autorizado e executado.
 *
 * As atividades vêm do `seed_demo`, descobertas por `fichaAtividadeFixture`;
 * nada é gravado. A compressão da foto está em `atividades.spec.ts`, junto
 * dos outros uploads.
 */

let fx: FichaAtividadeFixture;

test.beforeAll(() => {
  fx = descobrirAtividadesDaFicha();
});

const caminho = (r: Response) => new URL(r.url()).pathname;

/** Abre um `Select` do design system pelo id e escolhe a opção pelo valor do rótulo. */
async function escolher(page: Page, id: string, opcao: string | RegExp) {
  await page.locator(`#${id}`).click();
  await page.getByRole("option", { name: opcao }).first().click();
}

/** Espera a próxima listagem com o parâmetro e devolve o `count`. */
function proximaListagem(page: Page, parametro: string, valor: string | null) {
  return page.waitForResponse((r) => {
    if (caminho(r) !== "/api/v1/sgp/atividades/" || r.request().method() !== "GET") return false;
    return new URL(r.url()).searchParams.get(parametro) === valor;
  });
}

const contagem = async (r: Promise<Response>) => ((await (await r).json()) as { count: number }).count;

/** Valor exibido ao lado do rótulo numa `DefinitionList`. */
function valorDe(page: Page, escopo: string, rotulo: string) {
  return page.getByTestId(escopo).locator("dt", { hasText: new RegExp(`^${rotulo}$`) }).locator("xpath=following-sibling::dd[1]");
}

test.describe("Atividades — filtros do Plano de Trabalho (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("Meta, Submeta e Indicador filtram no backend, ficam na URL e se limpam juntos", async ({ page }) => {
    const { filtros: f } = fx;
    const lista = page.waitForResponse((r) => caminho(r) === "/api/v1/acoes/");
    const inicial = proximaListagem(page, "meta", null);
    await page.goto("/sgp/atividades");
    const acoes = ((await (await lista).json()) as {
      results: { meta: number; meta_numero: number; submeta: number; submeta_numero: string; indicador: number; indicador_detalhe: { codigo: string } }[];
    }).results;
    expect(await contagem(inicial)).toBe(f.total);

    const daMeta = acoes.find((a) => a.meta === f.meta)!;
    const daSubmeta = acoes.find((a) => a.submeta === f.submeta)!;
    const doIndicador = acoes.find((a) => a.indicador === f.indicador)!;

    // Meta.
    let resposta = proximaListagem(page, "meta", String(f.meta));
    await escolher(page, "atividades-filtro-meta", new RegExp(`^Meta ${daMeta.meta_numero} — `));
    expect(await contagem(resposta)).toBe(f.nMeta);
    await expect(page).toHaveURL(new RegExp(`[?&]meta=${f.meta}(&|$)`));

    // Submeta: as opções são só as da Meta escolhida.
    await page.locator("#atividades-filtro-submeta").click();
    const submetasDaMeta = [...new Set(acoes.filter((a) => a.meta === f.meta).map((a) => a.submeta_numero))];
    const listbox = page.getByRole("listbox");
    // As da Meta, mais "Todas as submetas da meta".
    await expect(listbox.getByRole("option")).toHaveCount(submetasDaMeta.length + 1);
    for (const numero of submetasDaMeta) {
      await expect(listbox.getByRole("option", { name: new RegExp(`^${numero.replace(".", "\\.")} — `) })).toHaveCount(1);
    }
    await page.keyboard.press("Escape");
    resposta = proximaListagem(page, "submeta", String(f.submeta));
    await escolher(page, "atividades-filtro-submeta", new RegExp(`^${daSubmeta.submeta_numero.replace(".", "\\.")} — `));
    expect(await contagem(resposta)).toBe(f.nSubmeta);

    // A URL guarda os filtros: recarregar refaz a mesma consulta.
    const recarregada = proximaListagem(page, "submeta", String(f.submeta));
    await page.reload();
    expect(await contagem(recarregada)).toBe(f.nSubmeta);
    await expect(page.locator("#atividades-filtro-submeta")).toContainText(`${daSubmeta.submeta_numero} — `);

    // Limpar tira os três; depois o Indicador sozinho e combinado com a Meta.
    resposta = proximaListagem(page, "submeta", null);
    await page.getByRole("button", { name: "Limpar filtros" }).click();
    expect(await contagem(resposta)).toBe(f.total);
    await expect(page).not.toHaveURL(/[?&](meta|submeta|indicador)=/);

    resposta = proximaListagem(page, "indicador", String(f.indicador));
    await escolher(page, "atividades-filtro-indicador", new RegExp(`^${doIndicador.indicador_detalhe.codigo} — `));
    expect(await contagem(resposta)).toBe(f.nIndicador);

    resposta = proximaListagem(page, "meta", String(f.meta));
    await escolher(page, "atividades-filtro-meta", new RegExp(`^Meta ${daMeta.meta_numero} — `));
    expect(await contagem(resposta)).toBe(f.nMetaEIndicador);
  });
});

test.describe("Ficha da atividade (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("sem coordenadas, parceiros, participantes e resultados, a ficha diz isso; início e fim com hora", async ({ page }) => {
    const detalhe = page.waitForResponse((r) => caminho(r) === `/api/v1/sgp/atividades/${fx.vazia}/`);
    await page.goto(`/sgp/atividades/${fx.vazia}/`);
    const atividade = (await (await detalhe).json()) as { data_inicio: string; data_fim: string };

    const dataHora = (iso: string) => {
      const d = new Date(iso);
      const p = (n: number) => String(n).padStart(2, "0");
      return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} às ${p(d.getHours())}:${p(d.getMinutes())}`;
    };
    await expect(page.getByTestId("atividade-inicio")).toHaveText(dataHora(atividade.data_inicio));
    await expect(page.getByTestId("atividade-fim")).toHaveText(dataHora(atividade.data_fim));

    await expect(valorDe(page, "atividade-equipe-local", "Coordenadas")).toHaveText("—");
    await expect(valorDe(page, "atividade-equipe-local", "Parceiros")).toHaveText("—");
    await expect(page.getByTestId("atividade-participantes-vazio")).toHaveText(
      "Nenhuma UFPA ou membro registrado como participante.",
    );
    await expect(page.getByTestId("atividade-resultados")).toContainText("Não registrado.");
  });

  test("a aba Demandas mostra rubricas e os valores estimado, autorizado e executado", async ({ page }) => {
    const lista = page.waitForResponse(
      (r) => caminho(r) === "/api/v1/sgd/demandas/" && new URL(r.url()).searchParams.get("atividade") === String(fx.comDemandaConcluida),
    );
    await page.goto(`/sgp/atividades/${fx.comDemandaConcluida}/?tab=demandas`);
    const demandas = ((await (await lista).json()) as {
      results: {
        id: number;
        status: string;
        valor_estimado_total: string;
        valor_autorizado_total: string;
        valor_pago_total: string;
        solicitacoes: { rubrica_nome: string }[];
      }[];
    }).results;
    expect(demandas.some((d) => d.status === "concluida"), "a fixture escolheu uma atividade com demanda concluída").toBe(true);

    const brl = (v: string) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    const sem = (s: string | null) => (s ?? "").replace(/\s/g, " ");
    for (const d of demandas) {
      await expect(page.getByTestId(`demanda-${d.id}-rubricas`)).toHaveText(
        [...new Set(d.solicitacoes.map((s) => s.rubrica_nome))].join(", ") || "Nenhuma solicitação",
      );
      await expect.poll(async () => sem(await page.getByTestId(`demanda-${d.id}-estimado`).textContent())).toBe(sem(brl(d.valor_estimado_total)));
      const autorizado = ["autorizada", "em_atendimento", "concluida"].includes(d.status) ? brl(d.valor_autorizado_total) : "—";
      const executado = d.status === "concluida" ? brl(d.valor_pago_total) : "—";
      await expect.poll(async () => sem(await page.getByTestId(`demanda-${d.id}-autorizado`).textContent())).toBe(sem(autorizado));
      await expect.poll(async () => sem(await page.getByTestId(`demanda-${d.id}-executado`).textContent())).toBe(sem(executado));
    }
  });
});
