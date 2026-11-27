import { expect, test, type Page, type Response } from "@playwright/test";
import { storageStatePath } from "./helpers/users";

/**
 * #446 (SGP-RF07; SGD-RF02) — a cadeia Ação → Submeta → Meta → Indicador do
 * Plano de Trabalho, só leitura, no formulário e na ficha da atividade e no
 * painel da demanda. O backend devolve a cadeia desde o #445 (PR #468).
 *
 * Só leitura: os testes não gravam nada. O esperado vem das respostas que a
 * própria tela recebe do backend real, observadas sem alteração.
 */

type AcaoDaLista = {
  id: number;
  numero: string;
  descricao: string;
  meta_numero: number;
  meta_titulo: string;
  submeta_numero: string;
  submeta_titulo: string;
  indicador_detalhe: { codigo: string; nome: string; unidade_medida: string };
};

type Cadeia = {
  acao: string;
  submeta: string;
  meta: string;
  indicador: string;
};

const caminho = (r: Response) => new URL(r.url()).pathname;

function daLista(a: AcaoDaLista): Cadeia {
  return {
    acao: `${a.numero} — ${a.descricao}`,
    submeta: `${a.submeta_numero} — ${a.submeta_titulo}`,
    meta: `Meta ${a.meta_numero} — ${a.meta_titulo}`,
    indicador: `${a.indicador_detalhe.codigo} — ${a.indicador_detalhe.nome} (unidade: ${a.indicador_detalhe.unidade_medida})`,
  };
}

async function conferirCadeia(page: Page, prefixo: string, esperada: Cadeia) {
  for (const nivel of ["acao", "submeta", "meta", "indicador"] as const) {
    await expect(page.getByTestId(`${prefixo}-${nivel}`)).toHaveText(esperada[nivel]);
  }
}

test.describe("Cadeia do Plano de Trabalho — atividade (UGP)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("escolher a Ação mostra a cadeia na hora, e trocar a Ação troca a cadeia", async ({ page }) => {
    const lista = page.waitForResponse((r) => caminho(r) === "/api/v1/acoes/" && r.request().method() === "GET");
    await page.goto("/sgp/atividades/nova");
    const acoes = ((await (await lista).json()) as { results: AcaoDaLista[] }).results;

    // Duas Ações de Metas diferentes, para a troca mudar todos os níveis.
    const primeira = acoes[0];
    const outra = acoes.find((a) => a.meta_numero !== primeira.meta_numero);
    expect(outra, "o seed tem Ações em mais de uma Meta").toBeDefined();

    await expect(page.getByTestId("atividade-form-cadeia")).toHaveCount(0);
    const combo = page.locator("#atividade-acao");
    await combo.fill(primeira.numero);
    await page.getByRole("option", { name: `${primeira.numero} — ${primeira.descricao}` }).click();
    await conferirCadeia(page, "atividade-form-cadeia", daLista(primeira));

    await page.getByRole("button", { name: /^Remover ação/ }).click();
    await expect(page.getByTestId("atividade-form-cadeia")).toHaveCount(0);
    await page.locator("#atividade-acao").fill(outra!.numero);
    await page.getByRole("option", { name: `${outra!.numero} — ${outra!.descricao}` }).click();
    await conferirCadeia(page, "atividade-form-cadeia", daLista(outra!));
  });

  test("a ficha e a edição da atividade mostram os quatro níveis", async ({ page }) => {
    const lista = page.waitForResponse(
      (r) => caminho(r) === "/api/v1/sgp/atividades/" && r.request().method() === "GET",
    );
    await page.goto("/sgp/atividades");
    const [{ id }] = ((await (await lista).json()) as { results: { id: number }[] }).results;

    const detalhe = page.waitForResponse((r) => caminho(r) === `/api/v1/sgp/atividades/${id}/`);
    await page.goto(`/sgp/atividades/${id}/`);
    const { acao } = (await (await detalhe).json()) as {
      acao: {
        numero: string;
        descricao: string;
        meta: { numero: number; titulo: string };
        submeta: { numero: string; titulo: string };
        indicador: { codigo: string; nome: string; unidade_medida: string };
      };
    };
    const esperada: Cadeia = {
      acao: `${acao.numero} — ${acao.descricao}`,
      submeta: `${acao.submeta.numero} — ${acao.submeta.titulo}`,
      meta: `Meta ${acao.meta.numero} — ${acao.meta.titulo}`,
      indicador: `${acao.indicador.codigo} — ${acao.indicador.nome} (unidade: ${acao.indicador.unidade_medida})`,
    };
    await conferirCadeia(page, "atividade-cadeia", esperada);

    // Na edição, a cadeia da Ação gravada aparece antes de mexer no campo.
    await page.goto(`/sgp/atividades/${id}/editar`);
    await conferirCadeia(page, "atividade-form-cadeia", esperada);
  });
});

test.describe("Cadeia do Plano de Trabalho — demanda (FGD)", () => {
  test.use({ storageState: storageStatePath("fgd") });

  test("o painel da demanda mostra os quatro níveis do contexto", async ({ page }) => {
    const lista = page.waitForResponse(
      (r) => caminho(r) === "/api/v1/sgd/demandas/" && r.request().method() === "GET",
    );
    await page.goto("/sgd/demandas?visao=todas");
    const demandas = ((await (await lista).json()) as { results: { id: number }[] }).results;
    expect(demandas.length, "o seed tem demandas visíveis à FGD").toBeGreaterThan(0);

    const detalhe = page.waitForResponse((r) => caminho(r) === `/api/v1/sgd/demandas/${demandas[0].id}/`);
    await page.goto(`/sgd/demandas?visao=todas&demanda=${demandas[0].id}`);
    const { contexto: c } = (await (await detalhe).json()) as { contexto: Record<string, string | number> };

    await conferirCadeia(page, "painel-cadeia", {
      acao: `${c.acao_numero} — ${c.acao_descricao}`,
      submeta: `${c.submeta_numero} — ${c.submeta_titulo}`,
      meta: `Meta ${c.meta_numero} — ${c.meta_titulo}`,
      indicador: `${c.indicador_codigo} — ${c.indicador_nome} (unidade: ${c.indicador_unidade_medida})`,
    });
  });
});
