import NextAuth, { type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { JWT } from "@auth/core/jwt";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Extende os tipos padrão do Auth.js para incluir os tokens do Django
declare module "next-auth" {
  interface Session {
    accessToken: string;
    refreshToken: string;
    error?: "RefreshTokenExpired";
    user: {
      username: string;
      permissions: string[];
    } & DefaultSession["user"];
  }

  interface User {
    accessToken: string;
    refreshToken: string;
    username: string;
    email: string;
    permissions: string[];
  }
}

// Tipo interno do JWT — o Auth.js v5 beta usa Record<string, unknown>,
// então usamos um tipo local e fazemos type assertions nas callbacks.
type AppJWT = JWT & {
  accessToken: string;
  refreshToken: string;
  username: string;
  email: string;
  permissions: string[];
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
       * O login real (POST /api/v1/auth/login/) acontece no cliente (login/page.tsx),
       * que tem acesso total ao body da resposta (401 {code, message}, 429 Retry-After).
       * O authorize() recebe os tokens já validados e só busca os dados do usuário.
       */
      credentials: {
        access: { label: "Access token", type: "text" },
        refresh: { label: "Refresh token", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.access || !credentials?.refresh) return null;

        const access = credentials.access as string;
        const refresh = credentials.refresh as string;

        // Busca dados completos do usuário (email + permissões)
        let username = "";
        let email = "";
        let permissions: string[] = [];
        try {
          const meRes = await fetch(`${BASE_URL}/api/v1/auth/me/`, {
            headers: { Authorization: `Bearer ${access}` },
          });
          if (meRes.ok) {
            const me: { id: number; username: string; email: string; permissions: string[] } =
              await meRes.json();
            username = me.username;
            email = me.email;
            permissions = me.permissions;
          }
        } catch {
          // Segue sem dados extras caso a chamada falhe
        }

        return {
          id: username || "user",
          username,
          email,
          permissions,
          accessToken: access,
          refreshToken: refresh,
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
        t.username = user.username;
        t.email = user.email;
        t.permissions = user.permissions;
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

    // Expõe accessToken e username na session do cliente
    async session({ session, token }) {
      const t = token as AppJWT;
      session.accessToken = t.accessToken;
      session.refreshToken = t.refreshToken;
      session.user.username = t.username;
      session.user.email = t.email;
      session.user.permissions = t.permissions;
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
