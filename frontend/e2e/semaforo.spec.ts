import { expect, test } from "@playwright/test";

/**
 * Teste de componente do SemaforoBadge, rodado sobre a página /styleguide.
 *
 * O projeto não tem runner de teste de componente (só Playwright E2E), e montar
 * um para verificar um mapeamento de três cores custaria mais do que resolve.
 * O styleguide já renderiza os quatro níveis fora de qualquer contexto de dado,
 * que é exatamente o isolamento que um teste de componente busca.
 *
 * A comparação é feita contra as VARIÁVEIS do design system resolvidas no
 * navegador, e não contra hexadecimais escritos aqui: um teste que repetisse
 * "#1b5e3b" passaria a validar a cópia, não o token — e continuaria verde
 * depois de alguém trocar a paleta só em globals.css.
 */

type Amostra = {
  nivel: string;
  color: string;
  backgroundColor: string;
  borderColor: string;
  esperadoTexto: string;
  esperadoFundo: string;
};

/** nível → par de tokens (texto, fundo) que o design system manda usar. */
const TOKENS: Record<string, [string, string]> = {
  verde: ["--color-success-text", "--color-success-bg"],
  amarelo: ["--color-warning-text", "--color-warning-bg"],
  vermelho: ["--color-error-text", "--color-error-bg"],
  "sem-dado": ["--color-neutral-text", "--color-neutral-bg"],
};

async function amostrarBadges(
  page: import("@playwright/test").Page,
  tokens: Record<string, [string, string]>,
): Promise<Amostra[]> {
  return page.evaluate((mapa) => {
    /**
     * Resolve uma custom property passando por um elemento real: assim o valor
     * do token e a cor computada do badge saem no MESMO formato do navegador
     * (`rgb(...)`), e a comparação não depende de normalizar hex na mão.
     */
    function resolver(nomeVar: string): string {
      const probe = document.createElement("span");
      probe.style.color = `var(${nomeVar})`;
      document.body.appendChild(probe);
      const valor = getComputedStyle(probe).color;
      probe.remove();
      return valor;
    }

    const badges = Array.from(
      document.querySelectorAll('[data-testid="semaforo-badge"]'),
    );

    return badges.map((el) => {
      const nivel = el.getAttribute("data-nivel") ?? "";
      const [varTexto, varFundo] = mapa[nivel] ?? ["", ""];
      const cs = getComputedStyle(el);
      return {
        nivel,
        color: cs.color,
        backgroundColor: cs.backgroundColor,
        // A borda é uniforme; qualquer lado serve de amostra.
        borderColor: cs.borderTopColor,
        esperadoTexto: resolver(varTexto),
        esperadoFundo: resolver(varFundo),
      };
    });
  }, tokens);
}

// /styleguide fica fora do grupo (protected) — não precisa de sessão.
test.describe("SemaforoBadge — mapeamento de cores do design system", () => {
  for (const tema of ["light", "dark"] as const) {
    test(`cores dos badges seguem a paleta semântica (tema ${tema})`, async ({
      page,
    }) => {
      await page.goto("/styleguide");

      await page.evaluate((t) => {
        document.documentElement.setAttribute("data-theme", t);
      }, tema);

      const badges = page.getByTestId("semaforo-badge");
      await expect(badges.first()).toBeVisible();

      const amostras = await amostrarBadges(page, TOKENS);

      // Os quatro níveis precisam estar na página — se o styleguide deixar de
      // renderizar um deles, o teste não pode passar por omissão.
      const niveis = amostras.map((a) => a.nivel);
      for (const esperado of Object.keys(TOKENS)) {
        expect(niveis, `nível "${esperado}" ausente do styleguide`).toContain(
          esperado,
        );
      }

      for (const a of amostras) {
        expect(a.esperadoTexto, `token de texto vazio para "${a.nivel}"`).not.toBe(
          "",
        );
        expect(a.color, `cor de texto do nível "${a.nivel}"`).toBe(
          a.esperadoTexto,
        );
        expect(a.backgroundColor, `fundo do nível "${a.nivel}"`).toBe(
          a.esperadoFundo,
        );
        expect(a.borderColor, `borda do nível "${a.nivel}"`).toBe(
          a.esperadoTexto,
        );
      }

      // Verde, amarelo e vermelho precisam ser DISTINTOS entre si: um mapa que
      // apontasse dois níveis para o mesmo token passaria em todas as
      // igualdades acima e deixaria o semáforo sem informação.
      const cores = new Set(
        amostras
          .filter((a) => a.nivel !== "sem-dado")
          .map((a) => `${a.color}|${a.backgroundColor}`),
      );
      expect(cores.size).toBe(3);
    });
  }
});
