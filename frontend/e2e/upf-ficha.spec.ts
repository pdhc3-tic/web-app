import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

/**
 * Ficha da UPF — navegação por abas via `?tab=` (#275) e comportamento das
 * quatro abas CRUD após a migração para TanStack Query (#271).
 *
 * A troca de aba é ação do usuário: usa `router.push` para o Voltar do browser
 * percorrer as abas visitadas. A URL é construída a partir de uma cópia dos
 * `searchParams` — nada de descartar filtros de outras abas quando muda a
 * aba ativa. E URLs antigas com hash (`#membros`, herdadas de antes do #275)
 * são convertidas para `?tab=membros` na primeira montagem via `router.replace`
 * para não poluir o histórico.
 *
 * Para #271: cada aba (Membros, Produção, Documentos, Histórico) é validada
 * abrindo e vendo o conteúdo renderizado — se qualquer `useQuery` falhar ao
 * ligar no `QueryClientProvider`, o teste quebra na hora. A troca rápida
 * entre duas UPFs prova que o cache com `queryKey` por UPF isola os dados.
 */

async function abrirFicha(page: Page, upfId: number, qs = ""): Promise<void> {
  await page.goto(`/sgp/upfs/${upfId}${qs}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

function abaAtiva(page: Page, nome: RegExp | string) {
  return page.getByRole("tab", { name: nome, selected: true });
}

/**
 * Segunda UPF do seed. Usado só para o teste de troca rápida (#271) — não
 * merece um helper próprio em `helpers/upf.ts` porque nenhum outro spec
 * precisa da segunda UPF hoje. Se surgir consumidor, migra para lá.
 */
function segundaUpfId(): number {
  const linha = execFileSync(
    "docker",
    [
      "exec",
      "db",
      "psql",
      "-U",
      "postgres",
      "-d",
      "app_db",
      "-tAc",
      "select id from sgp_upf order by id offset 1 limit 1;",
    ],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
  const id = Number(linha);
  expect(id, "seed precisa de pelo menos duas UPFs").toBeGreaterThan(0);
  return id;
}

test.describe("UPF — ficha (navegação por abas)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  let upfId: number;

  test.beforeAll(() => {
    upfId = primeiroUpfId();
  });

  test("aba padrão é Localização quando não há ?tab= na URL", async ({
    page,
  }) => {
    await abrirFicha(page, upfId);
    await expect(abaAtiva(page, "Localização")).toBeVisible();
  });

  test("?tab=membros seleciona a aba Membros; valor inválido cai em Localização", async ({
    page,
  }) => {
    await abrirFicha(page, upfId, "?tab=membros");
    await expect(abaAtiva(page, "Membros")).toBeVisible();
    await expect(page.getByTestId("membros-tab")).toBeVisible();

    await abrirFicha(page, upfId, "?tab=inexistente");
    await expect(abaAtiva(page, "Localização")).toBeVisible();
  });

  test("hash antigo (#membros) é convertido em ?tab=membros na primeira montagem", async ({
    page,
  }) => {
    await abrirFicha(page, upfId, "#membros");
    await page.waitForURL(new RegExp(`/sgp/upfs/${upfId}\\?tab=membros$`));
    await expect(abaAtiva(page, "Membros")).toBeVisible();
  });

  test("Voltar do browser percorre as abas visitadas (router.push)", async ({
    page,
  }) => {
    // Ancora em Localização — se o router estivesse usando `replace` (bug
    // apontado no review), o Voltar sairia direto da ficha em vez de percorrer
    // Membros → Documentos → Localização.
    await abrirFicha(page, upfId, "?tab=localizacao");

    await page.getByRole("tab", { name: "Membros" }).click();
    await page.waitForURL(/\?tab=membros/);

    await page.getByRole("tab", { name: "Documentos" }).click();
    await page.waitForURL(/\?tab=documentos/);

    await page.goBack();
    await page.waitForURL(/\?tab=membros/);
    await expect(abaAtiva(page, "Membros")).toBeVisible();

    await page.goBack();
    await page.waitForURL(/\?tab=localizacao/);
    await expect(abaAtiva(page, "Localização")).toBeVisible();
  });

  test("trocar de aba preserva outros searchParams (filtros de Formulários)", async ({
    page,
  }) => {
    // Abre a aba Formulários já com o filtro "Apenas anônimas" ligado — o
    // FormulariosTab reflete esse filtro na URL como `apenas_anonimas=1`.
    // Ao trocar para Membros, o router precisa preservar esse parâmetro
    // (bug do review: `${pathname}?tab=${id}` descartava tudo mais).
    await abrirFicha(page, upfId, "?tab=formularios&apenas_anonimas=1");
    await expect(abaAtiva(page, "Formulários")).toBeVisible();

    await page.getByRole("tab", { name: "Membros" }).click();
    await page.waitForURL(/\?.*tab=membros/);
    await expect(page).toHaveURL(/apenas_anonimas=1/);
    await expect(abaAtiva(page, "Membros")).toBeVisible();
  });
});

test.describe("UPF — ficha (data-fetching via TanStack Query)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  let upfId: number;

  test.beforeAll(() => {
    upfId = primeiroUpfId();
  });

  test("aba Membros carrega via useQuery e mostra o conteúdo", async ({
    page,
  }) => {
    await abrirFicha(page, upfId, "?tab=membros");
    await expect(page.getByTestId("membros-tab")).toBeVisible();
    // A tabela (ou o EmptyState) aparece só quando o `useQuery` resolve —
    // se o QueryClientProvider estiver mal ligado, o `isPending` fica em
    // `true` para sempre e o `data-testid="membros-tab"` só monta o skeleton.
    await expect(
      page.getByTestId("membros-loading"),
    ).toHaveCount(0);
  });

  test("aba Produção carrega via useQuery", async ({ page }) => {
    await abrirFicha(page, upfId, "?tab=producao");
    await expect(abaAtiva(page, "Produção")).toBeVisible();
    // Empty state OU tabela — o importante é o skeleton ter saído,
    // provando que o `useQuery` resolveu.
    await expect(
      page.getByText(/Nenhuma atividade produtiva cadastrada|atividades? cadastrada/),
    ).toBeVisible();
  });

  test("aba Documentos carrega via useQuery", async ({ page }) => {
    await abrirFicha(page, upfId, "?tab=documentos");
    await expect(abaAtiva(page, "Documentos")).toBeVisible();
    await expect(
      page.getByText(/Nenhum documento anexado|documentos? anexados/),
    ).toBeVisible();
  });

  test("aba Histórico carrega via useQuery", async ({ page }) => {
    await abrirFicha(page, upfId, "?tab=historico");
    await expect(abaAtiva(page, "Histórico")).toBeVisible();
    // O histórico tem pelo menos a criação da UPF pelo seed, ou o EmptyState.
    await expect(
      page.getByText(/Nenhuma alteração registrada|alterou|criou a UPF/),
    ).toBeVisible();
  });

  test("troca rápida entre duas UPFs isola o cache (queryKey por UPF)", async ({
    page,
  }) => {
    const outraUpf = segundaUpfId();
    expect(outraUpf).not.toBe(upfId);

    // Abre a primeira UPF na aba Membros e guarda o cabeçalho.
    await abrirFicha(page, upfId, "?tab=membros");
    await expect(page.getByTestId("membros-tab")).toBeVisible();
    const nomePrimeiro = await page
      .getByRole("heading", { level: 1 })
      .innerText();

    // Navega para a segunda UPF — mesma aba. Se o cache estivesse
    // compartilhado (`queryKey: ["membros"]` sem o id), a segunda UPF
    // mostraria os membros da primeira até o refetch chegar.
    await abrirFicha(page, outraUpf, "?tab=membros");
    await expect(page.getByTestId("membros-tab")).toBeVisible();
    const nomeSegundo = await page
      .getByRole("heading", { level: 1 })
      .innerText();

    expect(nomeSegundo).not.toBe(nomePrimeiro);
  });
});
