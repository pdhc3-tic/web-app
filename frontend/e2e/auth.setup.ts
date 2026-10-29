import fs from "node:fs";
import path from "node:path";
import { expect, test as setup, type Browser } from "@playwright/test";
import { esperarHidratacao } from "./helpers/hidratacao";
import { USERS, storageStatePath, type UserKey } from "./helpers/users";

/**
 * O /api/v1/auth/login/ do Django tem rate limit por IP e o bloqueio pode
 * passar de 3 minutos. Rodar a suíte várias vezes seguidas esbarra nele, então
 * o setup lê o tempo informado na própria tela e espera a janela reabrir.
 */
const TENTATIVAS = 3;
const ESPERA_PADRAO_S = 45;
const ESPERA_MAXIMA_S = 300;

/** Extrai os segundos de "Muitas tentativas. Tente novamente em 236 segundos." */
function segundosDeEspera(mensagem: string): number {
  const m = /em (\d+) segundos?/.exec(mensagem);
  if (!m) return ESPERA_PADRAO_S;
  return Math.min(parseInt(m[1], 10) + 3, ESPERA_MAXIMA_S);
}

/**
 * Reaproveita a sessão gravada quando ela ainda vale. O `/api/auth/session`
 * do Auth.js renova o access token pelo refresh token; só quando o refresh
 * também venceu (`RefreshTokenExpired`) ou o e-mail não bate é que o login
 * pela tela é necessário — e ele é o que esbarra no rate limit.
 */
async function sessaoGravadaValida(browser: Browser, key: UserKey): Promise<boolean> {
  const destino = storageStatePath(key);
  if (!fs.existsSync(destino)) return false;
  const contexto = await browser.newContext({
    storageState: destino,
    baseURL: setup.info().project.use.baseURL,
  });
  try {
    const res = await contexto.request.get("/api/auth/session");
    if (!res.ok()) return false;
    const sessao = (await res.json().catch(() => null)) as
      | { user?: { email?: string }; error?: string }
      | null;
    if (!sessao?.user || sessao.error || sessao.user.email !== USERS[key].email) return false;
    // A renovação pode ter trocado o cookie da sessão: grava o estado novo.
    await contexto.storageState({ path: destino });
    return true;
  } finally {
    await contexto.close();
  }
}

for (const key of Object.keys(USERS) as UserKey[]) {
  setup(`autentica ${key}`, async ({ page, browser }) => {
    setup.setTimeout(20 * 60_000);
    if (await sessaoGravadaValida(browser, key)) return;
    const { email, password } = USERS[key];
    // O overlay do Next dev também expõe role=alert; escopar no <main> isola
    // o alerta do formulário de login.
    const alerta = page.locator("main").getByRole("alert");

    for (let tentativa = 1; tentativa <= TENTATIVAS; tentativa++) {
      await page.goto("/login");
      await esperarHidratacao(page);
      await page.locator("#email").fill(email);
      await page.locator("#password").fill(password);
      await page.getByRole("button", { name: "Entrar" }).click();

      try {
        await page.waitForURL("**/dashboard", { timeout: 30_000 });
        break;
      } catch (erro) {
        const motivo = (await alerta.first().innerText().catch(() => "")).trim();
        if (tentativa === TENTATIVAS) {
          throw new Error(
            `Login de ${email} falhou após ${TENTATIVAS} tentativas` +
              (motivo ? `: ${motivo}` : ` (${String(erro)})`),
          );
        }
        await page.waitForTimeout(segundosDeEspera(motivo) * 1000);
      }
    }

    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

    const destino = storageStatePath(key);
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    await page.context().storageState({ path: destino });
  });
}
