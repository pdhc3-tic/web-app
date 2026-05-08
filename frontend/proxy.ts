import { auth } from "@/auth";
import { NextResponse } from "next/server";
import type { NextAuthRequest } from "next-auth";

const PUBLIC_PATHS = ["/login", "/esqueci-minha-senha", "/redefinir-senha"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
}

export default auth((req: NextAuthRequest) => {
  const { pathname } = req.nextUrl;
  const session = req.auth;
  const hasError = (session as { error?: string } | null)?.error === "RefreshTokenExpired";

  // Sem sessão ou refresh expirou → redireciona para login preservando a URL de destino
  if ((!session || hasError) && !isPublicPath(pathname)) {
    const loginUrl = new URL("/login", req.nextUrl);
    loginUrl.searchParams.set("next", req.nextUrl.pathname + req.nextUrl.search);
    return NextResponse.redirect(loginUrl);
  }

  // Autenticado tentando acessar rota pública → redireciona para dashboard
  if (session !== null && !hasError && isPublicPath(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", req.nextUrl));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|.*\\.(?:png|svg|ico|jpg)$).*)"],
};
