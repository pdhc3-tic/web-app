import NextAuth, { type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { JWT } from "@auth/core/jwt";
import { CredentialsSignin } from "@auth/core/errors";
import type { Perfil, Territorio } from "@/app/lib/auth/types";

// API_INTERNAL_URL é usado server-side (ex: dentro do container Docker, http://backend:8000).
const BASE_URL =
  process.env.API_INTERNAL_URL ??
  "http://backend:8000";

// Extende os tipos padrão do Auth.js para incluir os tokens do Django
declare module "next-auth" {
  interface Session {
    accessToken: string;
    refreshToken: string;
    error?: "RefreshTokenExpired";
    user: {
      id: string;
      nome_completo: string;
      foto_url: string;
      perfis: Perfil[];
      territorios: Territorio[];
    } & DefaultSession["user"];
  }

  interface User {
    accessToken: string;
    refreshToken: string;
    id: string;
    nome_completo: string;
    email: string;
    foto_url: string;
    perfis: Perfil[];
    territorios: Territorio[];
  }
}

// Tipo interno do JWT — o Auth.js v5 beta usa Record<string, unknown>,
// então usamos um tipo local e fazemos type assertions nas callbacks.
type AppJWT = JWT & {
  accessToken: string;
  refreshToken: string;
  id: string;
  nome_completo: string;
  email: string;
  foto_url: string;
  perfis: Perfil[];
  territorios: Territorio[];
  accessTokenExpiresAt: number;
  error?: "RefreshTokenExpired";
};

/**
 * Tenta renovar o access token Django usando o refresh token.
 * Retorna o novo access token ou null se o refresh expirou.
 */
async function refreshDjangoToken(refreshToken: string): Promise<{ access: string; refresh: string } | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/v1/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data: { access_token: string; refresh_token: string } = await res.json();
    return { access: data.access_token, refresh: data.refresh_token }
  } catch {
    return null;
  }
}

/**
 * Decodifica o campo `exp` do JWT do Django (sem verificar assinatura —
 * isso é feito pelo Django a cada requisição autenticada).
 */
function getTokenExpiry(token: string): number {
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64url").toString()
    );
    return (payload.exp as number) * 1000; // converte para ms
  } catch {
    return 0;
  }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      /*
       * O authorize() chama POST /api/v1/auth/login/ diretamente, server-side,
       * usando a URL interna (API_INTERNAL_URL). Os tokens JWT nunca chegam ao
       * browser. Erros são comunicados ao cliente via CredentialsSignin.code.
       */
      credentials: {
        email: { label: "E-mail", type: "email" },
        password: { label: "Senha", type: "password" },
      },
      async authorize(credentials) {
        const email = (credentials?.email as string) ?? "";
        const password = (credentials?.password as string) ?? "";
        if (!email || !password) return null;

        // 1. Autentica no Django
        let loginRes: Response;
        try {
          loginRes = await fetch(`${BASE_URL}/api/v1/auth/login/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, senha: password }),
          });
        } catch {
          const err = new CredentialsSignin();
          err.code = "network_error";
          throw err;
        }

        if (loginRes.status === 429) {
          let retryAfter = 60;
          try {
            const body: { retry_after?: number } = await loginRes.json();
            retryAfter = body.retry_after ?? 60;
          } catch { /* usa o padrão */ }
          const err = new CredentialsSignin();
          err.code = `rate_limited:${retryAfter}`;
          throw err;
        }

        if (!loginRes.ok) {
          const err = new CredentialsSignin();
          err.code = "invalid_credentials";
          throw err;
        }

        const tokens: { access_token: string; refresh_token: string } =
          await loginRes.json();

        // 2. Busca dados completos do usuário
        let id = "";
        let nome_completo = "";
        let userEmail = "";
        let foto_url = "";
        let perfis: Perfil[] = [];
        let territorios: Territorio[] = [];
        try {
          const meRes = await fetch(`${BASE_URL}/api/v1/auth/me/`, {
            headers: { Authorization: `Bearer ${tokens.access_token}` },
          });
          if (meRes.ok) {
            const me: {
              id: number;
              nome_completo: string;
              email: string;
              foto_url: string;
              perfis: Perfil[];
              territorios: Territorio[];
            } = await meRes.json();
            id = me.id.toString();
            nome_completo = me.nome_completo;
            userEmail = me.email;
            foto_url = me.foto_url;
            perfis = me.perfis;
            territorios = me.territorios;
          }
        } catch {
          // Segue sem dados extras caso a chamada falhe
        }

        return {
          id,
          nome_completo,
          email: userEmail,
          foto_url,
          perfis,
          territorios,
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
        };
      },
    }),
    // Para adicionar Google no futuro:
    // Google({ clientId: process.env.GOOGLE_CLIENT_ID, clientSecret: process.env.GOOGLE_CLIENT_SECRET })
    //
    // Para Gov.br (OIDC):
    // import GovBr from "next-auth/providers/govbr"  (ou provider customizado OIDC)
  ],

  callbacks: {
    // Persiste os tokens Django dentro do JWT do Auth.js
    async jwt({ token, user }) {
      const t = token as AppJWT;

      if (user) {
        t.accessToken = user.accessToken;
        t.refreshToken = user.refreshToken;
        t.id = user.id;
        t.nome_completo = user.nome_completo;
        t.email = user.email;
        t.foto_url = user.foto_url;
        t.perfis = user.perfis;
        t.territorios = user.territorios;
        t.accessTokenExpiresAt = getTokenExpiry(user.accessToken);
        return t;
      }

      // Token ainda válido — passa direto
      if (Date.now() < t.accessTokenExpiresAt) {
        return t;
      }

      // Access token expirado — tenta renovar silenciosamente
      const tokens = await refreshDjangoToken(t.refreshToken);

      if (tokens) {
        t.accessToken = tokens.access
        t.refreshToken = tokens.refresh
        t.accessTokenExpiresAt = getTokenExpiry(tokens.access);
        return t;
      }

      // Refresh também expirou — força novo login
      return { ...t, error: "RefreshTokenExpired" as const };
    },

    // Expõe accessToken e email na session do cliente
    async session({ session, token }) {
      const t = token as AppJWT;
      session.accessToken = t.accessToken;
      session.refreshToken = t.refreshToken;
      session.user.id = t.id;
      session.user.nome_completo = t.nome_completo;
      session.user.email = t.email;
      session.user.foto_url = t.foto_url;
      session.user.perfis = t.perfis;
      session.user.territorios = t.territorios;
      if (t.error) {
        session.error = t.error;
      }
      return session;
    },
  },

  pages: {
    signIn: "/login",
  },
});
