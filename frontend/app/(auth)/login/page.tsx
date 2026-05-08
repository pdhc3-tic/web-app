"use client";
import { useState, useEffect, useTransition } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type FieldErrors = { email?: string; password?: string };

// Spinner inline conforme padrão PDHC (seção 6.1 — estado Carregando)
function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12" cy="12" r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";

  const [pending, startTransition] = useTransition();
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  // Countdown para 429 — enquanto > 0, botão fica bloqueado
  const [retryAfter, setRetryAfter] = useState(0);

  useEffect(() => {
    if (retryAfter <= 0) return;
    const id = setInterval(() => {
      setRetryAfter((s) => {
        if (s <= 1) { clearInterval(id); return 0; }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [retryAfter]);

  function validate(email: string, password: string): FieldErrors {
    const errs: FieldErrors = {};
    if (!EMAIL_RE.test(email)) errs.email = "Informe um e-mail válido.";
    if (!password) errs.password = "A senha não pode ser vazia.";
    return errs;
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (retryAfter > 0) return;

    const form = e.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement).value.trim();
    const password = (form.elements.namedItem("password") as HTMLInputElement).value;

    const errs = validate(email, password);
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setGlobalError(null);
      return;
    }
    setFieldErrors({});
    setGlobalError(null);

    startTransition(async () => {
      // Passo 1 — chama o Django diretamente para ter acesso ao body completo da resposta
      let res: Response;
      try {
        res = await fetch(`${BASE_URL}/api/v1/auth/login/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, senha: password }),
        });
      } catch {
        setGlobalError("Não foi possível conectar ao servidor. Tente novamente.");
        return;
      }

      if (res.status === 429) {
        const retryHeader = res.headers.get("Retry-After");
        const seconds = retryHeader ? parseInt(retryHeader, 10) : 60;
        setRetryAfter(isNaN(seconds) ? 60 : seconds);
        return;
      }

      if (!res.ok) {
        try {
          // Arq. §5 define {code, message}. Simple JWT usa {detail} — fallback para compatibilidade
          const body: { code?: string; message?: string; detail?: string } = await res.json();
          setGlobalError(body.message ?? body.detail ?? "Usuário ou senha inválidos.");
        } catch {
          setGlobalError("Usuário ou senha inválidos.");
        }
        return;
      }

      const tokens: { access_token: string; refresh_token: string } = await res.json();

      // Passo 2 — entrega os tokens ao next-auth para criar a sessão (cookies HTTP-only)
      const result = await signIn("credentials", {
        access: tokens.access_token,
        refresh: tokens.refresh_token,
        redirect: false,
      });

      if (result?.error) {
        setGlobalError("Erro ao iniciar sessão. Tente novamente.");
        return;
      }

      router.push(next);
    });
  }

  const isBlocked = pending || retryAfter > 0;

  const inputBase =
    "h-10 w-full rounded-md border px-3 text-sm text-foreground bg-surface outline-none transition" +
    " focus:ring-2 focus:ring-primary/15 focus:border-primary" +
    " border-border placeholder:text-text-muted";
  const inputErrorCls = "border-error focus:ring-error/20 focus:border-error";

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm bg-surface rounded-lg border border-border shadow-sm p-8">

        {/* TODO: substituir pelo componente <Logo /> quando o arquivo da marca estiver disponível */}
        <div className="flex justify-center mb-7">
          <div className="w-32 h-12 bg-surface-muted rounded flex items-center justify-center">
            <span className="text-xs text-text-muted select-none">Logo PDHC</span>
          </div>
        </div>

        <h1 className="text-xl font-semibold text-primary mb-6">Entrar</h1>

        {/* Erro geral — aria-live para leitores de tela (PDHC seção 9.5) */}
        {(globalError || retryAfter > 0) && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-5 flex items-start gap-2 rounded-md border border-error bg-error-bg px-3 py-2.5"
          >
            <svg className="mt-0.5 h-4 w-4 shrink-0 text-error" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <p className="text-sm text-error">
              {retryAfter > 0
                ? `Muitas tentativas. Tente novamente em ${retryAfter} segundo${retryAfter !== 1 ? "s" : ""}.`
                : globalError}
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-sm font-medium text-foreground">
              E-mail
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              aria-invalid={!!fieldErrors.email}
              aria-describedby={fieldErrors.email ? "error-email" : undefined}
              className={`${inputBase} ${fieldErrors.email ? inputErrorCls : ""}`}
            />
            {fieldErrors.email && (
              <p id="error-email" className="text-xs text-error mt-0.5">{fieldErrors.email}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm font-medium text-foreground">
              Senha
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              aria-invalid={!!fieldErrors.password}
              aria-describedby={fieldErrors.password ? "error-password" : undefined}
              className={`${inputBase} ${fieldErrors.password ? inputErrorCls : ""}`}
            />
            {fieldErrors.password && (
              <p id="error-password" className="text-xs text-error mt-0.5">{fieldErrors.password}</p>
            )}
          </div>

          {/* Botão primário PDHC — fundo #1B5E3B, border-radius 6px (seção 6.1) */}
          <button
            type="submit"
            disabled={isBlocked}
            className="mt-1 h-10 rounded-md bg-primary text-white text-sm font-medium flex items-center justify-center gap-2 transition-colors hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pending ? (
              <>
                <Spinner />
                <span>Entrando...</span>
              </>
            ) : (
              "Entrar"
            )}
          </button>

          <div className="text-center">
            <Link
              href="/esqueci-minha-senha"
              className="text-sm text-text-muted hover:text-primary transition-colors"
            >
              Esqueci minha senha
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
