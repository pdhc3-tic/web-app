import type { Page } from "@playwright/test";

/**
 * Acesso direto à API real a partir da página, com o token da sessão do
 * NextAuth (Bearer) — o mesmo escopo que a tela enxerga.
 */

/** Abre a URL e devolve a origem da API, lida da primeira chamada que a tela faz a ela. */
export async function abrirComApi(page: Page, url: string): Promise<string> {
  const resposta = page.waitForResponse((r) => new URL(r.url()).pathname.startsWith("/api/v1/"));
  await page.goto(url);
  return new URL((await resposta).url()).origin;
}

/** GET autenticado na API; falha o teste se a resposta não for 2xx. */
export async function apiGet<T>(page: Page, origem: string, caminho: string): Promise<T> {
  return page.evaluate(
    async ({ url }) => {
      const sessao = await (await fetch("/api/auth/session")).json();
      const res = await fetch(url, { headers: { Authorization: `Bearer ${sessao.accessToken}` } });
      if (!res.ok) throw new Error(`${url} respondeu ${res.status}`);
      return res.json();
    },
    { url: `${origem}${caminho}` },
  ) as Promise<T>;
}

/**
 * Grava no localStorage a tarefa de exportação do job `id`, lido da API real,
 * do mesmo jeito que `useExportacao` grava ao iniciar. Recarregar a página faz
 * a tela retomar essa tarefa.
 */
export async function guardarTarefaDeExportacao(
  page: Page,
  origem: string,
  chave: string,
  id: number,
  filtros: Record<string, string> = {},
): Promise<void> {
  const exportacao = await apiGet(page, origem, `/api/v1/sgp/exportacoes/${id}/`);
  // O hook guarda a tarefa por usuário: `{chave}:{id do usuário da sessão}`.
  const sessao = await (await page.request.get("/api/auth/session")).json();
  await page.evaluate(
    ({ chave, valor }) => localStorage.setItem(chave, valor),
    { chave: `${chave}:${sessao.user.id}`, valor: JSON.stringify({ exportacao, filtros }) },
  );
}
