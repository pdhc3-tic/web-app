"use client";
import { useState, useEffect, useTransition } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import Spinner from "@/app/components/icons/Spinner";
import { AlertCircleIcon } from "@/app/components/icons";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type FieldErrors = { email?: string; password?: string };

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const resetSuccess = searchParams.get("reset") === "ok";

  const [pending, startTransition] = useTransition();
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [retryAfter, setRetryAfter] = useState(0);

  useEffect(() => {
    if (retryAfter <= 0) return;
    const id = setInterval(() => {
      setRetryAfter((s) => {
        if (s <= 1) {
          clearInterval(id);
          return 0;
        }
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
    const email = (
      form.elements.namedItem("email") as HTMLInputElement
    ).value.trim();
    const password = (form.elements.namedItem("password") as HTMLInputElement)
      .value;

    const errs = validate(email, password);
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setGlobalError(null);
      return;
    }
    setFieldErrors({});
    setGlobalError(null);

    startTransition(async () => {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        let code = "";
        try {
          if (result.url) {
            code =
              new URL(result.url, window.location.origin).searchParams.get(
                "code",
              ) ?? "";
          }
        } catch { /* ignora URL inválida */ }

        if (code.startsWith("rate_limited:")) {
          const seconds = parseInt(code.split(":")[1], 10);
          setRetryAfter(isNaN(seconds) ? 60 : seconds);
        } else if (code === "network_error") {
          setGlobalError(
            "Não foi possível conectar ao servidor. Tente novamente.",
          );
        } else {
          setGlobalError("Usuário ou senha inválidos.");
        }
        return;
      }

      router.push(next);
    });
  }

  const isBlocked = pending || retryAfter > 0;

  const inputBase =
    "h-12 w-full rounded-lg border border-border bg-transparent px-4 text-sm text-text outline-none placeholder:text-text-muted/70 transition" +
    " hover:border-text-muted/60 focus:border-primary focus:bg-surface focus:shadow-[0_0_0_4px_color-mix(in_srgb,var(--color-primary)_10%,transparent)]";
  const inputErrorCls =
    "border-error-text focus:border-error-text focus:shadow-[0_0_0_4px_color-mix(in_srgb,var(--color-error-text)_10%,transparent)]";

  return (
    <>
      <div className="mb-10">
        <h1 className="text-4xl font-semibold text-text leading-tight tracking-tight">
          Entrar
        </h1>
        <p className="mt-3 text-sm text-text-muted">
          Acesse o painel com suas credenciais.
        </p>
      </div>

      {resetSuccess && !globalError && retryAfter === 0 && (
        <div
          role="status"
          aria-live="polite"
          className="mb-6 rounded-lg bg-success-bg/60 px-3.5 py-2.5"
        >
          <p className="text-sm text-success-text">
            Senha redefinida com sucesso. Faça login com a nova senha.
          </p>
        </div>
      )}

      {(globalError || retryAfter > 0) && (
        <div
          role="alert"
          aria-live="polite"
          className="mb-6 flex items-start gap-2 rounded-lg bg-error-bg/60 px-3.5 py-2.5"
        >
          <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-error-text" />
          <p className="text-sm text-error-text">
            {retryAfter > 0
              ? `Muitas tentativas. Tente novamente em ${retryAfter} segundo${retryAfter !== 1 ? "s" : ""}.`
              : globalError}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
        <div className="flex flex-col gap-2">
          <label
            htmlFor="email"
            className="text-xs font-medium uppercase tracking-[0.15em] text-text-muted"
          >
            E-mail
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="seu.email@dominio.com"
            required
            aria-invalid={!!fieldErrors.email}
            aria-describedby={fieldErrors.email ? "error-email" : undefined}
            className={`${inputBase} ${fieldErrors.email ? inputErrorCls : ""}`}
          />
          {fieldErrors.email && (
            <p id="error-email" className="text-xs text-error-text">
              {fieldErrors.email}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <label
              htmlFor="password"
              className="text-xs font-medium uppercase tracking-[0.15em] text-text-muted"
            >
              Senha
            </label>
            <Link
              href="/esqueci-minha-senha"
              className="text-xs text-text-muted hover:text-primary transition-colors"
            >
              Esqueci minha senha
            </Link>
          </div>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            required
            aria-invalid={!!fieldErrors.password}
            aria-describedby={
              fieldErrors.password ? "error-password" : undefined
            }
            className={`${inputBase} ${fieldErrors.password ? inputErrorCls : ""}`}
          />
          {fieldErrors.password && (
            <p id="error-password" className="text-xs text-error-text">
              {fieldErrors.password}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={isBlocked}
          className="mt-3 h-12 rounded-lg bg-linear-to-br from-primary to-secondary text-white text-sm font-medium tracking-wide flex items-center justify-center gap-2 transition-all hover:shadow-lg hover:shadow-primary/25 active:shadow-md disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
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
      </form>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
