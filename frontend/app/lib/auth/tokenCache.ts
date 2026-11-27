import type { Session } from "next-auth";
import { getSession } from "next-auth/react";

/**
 * Token de acesso da sessão em memória (#448).
 *
 * O `apiClient` pedia `getSession()` a cada requisição, e cada uma é um
 * `GET /api/auth/session` que decifra e regrava o cookie. Uma tela com seis
 * chamadas à API fazia sete idas à sessão. Aqui o token fica guardado enquanto
 * estiver válido, e a sessão só é relida quando ele está para vencer: uma
 * única leitura, compartilhada pelas requisições que chegarem ao mesmo tempo.
 *
 * Quem alimenta o cache é o `SessionProvider` da área logada, com a sessão que
 * o servidor já leu, e as releituras feitas aqui.
 */

/** Margem antes do vencimento: o token não sai daqui a segundos de expirar. */
export const MARGEM_DE_VENCIMENTO_MS = 30_000;

type TokenEmCache = { sessao: Session; expiraEm: number };

let atual: TokenEmCache | null = null;
let leituraEmCurso: Promise<Session | null> | null = null;

/** `exp` do JWT do Django, em ms; 0 quando não dá para ler (o token é relido na próxima vez). */
export function vencimentoDoToken(token: string): number {
  try {
    const parte = token.split(".")[1];
    const base64 = parte.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

/** Guarda a sessão vinda do servidor ou de uma releitura. Sem token, limpa. */
export function guardarSessao(sessao: Session | null | undefined): void {
  // Só no navegador: no servidor, o módulo é um só para todos os usuários, e
  // o token de um não pode ficar onde a requisição de outro o leria.
  if (typeof window === "undefined") return;
  if (!sessao?.accessToken || sessao.error) {
    atual = null;
    return;
  }
  if (atual?.sessao.accessToken === sessao.accessToken) return;
  atual = { sessao, expiraEm: vencimentoDoToken(sessao.accessToken) };
}

export function esquecerSessao(): void {
  atual = null;
}

/**
 * Relê a sessão no servidor (que renova o token se for preciso). Chamadas
 * simultâneas esperam a mesma leitura.
 */
export function relerSessao(): Promise<Session | null> {
  if (!leituraEmCurso) {
    // Sem `broadcast`: as outras abas não precisam recarregar a sessão por isso.
    leituraEmCurso = getSession({ broadcast: false })
      .then((sessao) => {
        guardarSessao(sessao);
        return sessao;
      })
      .finally(() => {
        leituraEmCurso = null;
      });
  }
  return leituraEmCurso;
}

/** A sessão com um token que ainda vale; relê só quando falta ou está para vencer. */
export async function sessaoValida(agora: number = Date.now()): Promise<Session | null> {
  if (atual && atual.expiraEm - MARGEM_DE_VENCIMENTO_MS > agora) return atual.sessao;
  return relerSessao();
}
