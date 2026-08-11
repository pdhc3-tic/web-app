import type { Page } from "@playwright/test";

/**
 * Espera o React hidratar a página antes de interagir.
 *
 * Sem isso, um clique no botão de submit chega enquanto o `onSubmit` ainda não
 * está ligado e o browser faz o submit nativo do <form> — vira um GET com os
 * campos na query string, sem nenhum POST para o backend. Em dev (compilação
 * sob demanda) a janela para isso acontecer é larga o bastante para tornar o
 * teste intermitente.
 *
 * O sinal usado é a propriedade `__reactFiber$…` que o React grava nos nós do
 * DOM ao hidratar.
 */
export async function esperarHidratacao(
  page: Page,
  seletor = "form",
): Promise<void> {
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      return !!el && Object.keys(el).some((k) => k.startsWith("__reactFiber$"));
    },
    seletor,
    { timeout: 30_000 },
  );
}
