import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "next-auth";

/** #448: o token é reaproveitado e a sessão só é relida quando ele falta ou vence. */

const getSession = vi.fn();
vi.mock("next-auth/react", () => ({ getSession: (...args: unknown[]) => getSession(...args) }));

/** JWT só com o `exp` (segundos), no formato base64url do Django. */
function jwt(expSegundos: number): string {
  const payload = Buffer.from(JSON.stringify({ exp: expSegundos, user_id: 1 })).toString("base64url");
  return `cabecalho.${payload}.assinatura`;
}

function sessao(token: string, extra: Partial<Session> = {}): Session {
  return { accessToken: token, refreshToken: "r", expires: "", user: {} as Session["user"], ...extra } as Session;
}

const AGORA = 1_800_000_000_000;

async function modulo() {
  vi.resetModules();
  return import("./tokenCache");
}

beforeEach(() => getSession.mockReset());

describe("tokenCache (#448)", () => {
  it("lê o vencimento do JWT; token ilegível vence já", async () => {
    const { vencimentoDoToken } = await modulo();
    expect(vencimentoDoToken(jwt(1_800_000_600))).toBe(1_800_000_600_000);
    expect(vencimentoDoToken("não é jwt")).toBe(0);
  });

  it("com o token da sessão do servidor, nenhuma ida a /api/auth/session", async () => {
    const { guardarSessao, sessaoValida } = await modulo();
    const s = sessao(jwt(AGORA / 1000 + 600));
    guardarSessao(s);
    expect(await sessaoValida(AGORA)).toBe(s);
    expect(await sessaoValida(AGORA)).toBe(s);
    expect(getSession).not.toHaveBeenCalled();
  });

  it("perto de vencer (menos de 30 s), relê uma vez só para as requisições simultâneas", async () => {
    const { guardarSessao, sessaoValida } = await modulo();
    guardarSessao(sessao(jwt(AGORA / 1000 + 20)));
    const nova = sessao(jwt(AGORA / 1000 + 900));
    let responder: (s: Session) => void = () => {};
    getSession.mockReturnValueOnce(new Promise((r) => (responder = r)));

    const pedidos = [sessaoValida(AGORA), sessaoValida(AGORA), sessaoValida(AGORA)];
    responder(nova);
    expect(await Promise.all(pedidos)).toEqual([nova, nova, nova]);
    expect(getSession).toHaveBeenCalledTimes(1);
    expect(getSession).toHaveBeenCalledWith({ broadcast: false });

    // O token renovado fica no cache: a próxima não relê.
    expect(await sessaoValida(AGORA)).toBe(nova);
    expect(getSession).toHaveBeenCalledTimes(1);
  });

  it("sem sessão em cache, relê", async () => {
    const { sessaoValida } = await modulo();
    const s = sessao(jwt(AGORA / 1000 + 600));
    getSession.mockResolvedValueOnce(s);
    expect(await sessaoValida(AGORA)).toBe(s);
    expect(getSession).toHaveBeenCalledTimes(1);
  });

  it("sessão com erro de renovação ou sem token não fica no cache", async () => {
    const { guardarSessao, sessaoValida } = await modulo();
    guardarSessao(sessao(jwt(AGORA / 1000 + 600), { error: "RefreshTokenExpired" }));
    getSession.mockResolvedValueOnce(null);
    expect(await sessaoValida(AGORA)).toBeNull();
    expect(getSession).toHaveBeenCalledTimes(1);
  });

  it("esquecerSessao força a releitura (o caminho do 401)", async () => {
    const { esquecerSessao, guardarSessao, sessaoValida } = await modulo();
    guardarSessao(sessao(jwt(AGORA / 1000 + 600)));
    esquecerSessao();
    getSession.mockResolvedValueOnce(sessao(jwt(AGORA / 1000 + 900)));
    await sessaoValida(AGORA);
    expect(getSession).toHaveBeenCalledTimes(1);
  });
});
