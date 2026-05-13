"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MENSAGEM_GENERICA =
  "Se o e-mail estiver cadastrado, enviamos um link de redefinição.";

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

const inputBase =
  "h-10 w-full rounded-md border px-3 text-sm text-foreground bg-surface outline-none transition" +
  " focus:ring-2 focus:ring-primary/15 focus:border-primary" +
  " border-border placeholder:text-text-muted";
const inputErrorCls = "border-error focus:ring-error/20 focus:border-error";

export default function EsqueciMinhaSenhaPage() {
  const [pending, startTransition] = useTransition();
  const [emailError, setEmailError] = useState<string | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
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

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (retryAfter > 0) return;

    const email = (e.currentTarget.elements.namedItem("email") as HTMLInputElement).value.trim();

    if (!EMAIL_RE.test(email)) {
      setEmailError("Informe um e-mail válido.");
      setGeneralError(null);
      return;
    }
    setEmailError(null);
    setGeneralError(null);

    startTransition(async () => {
      let res: Response;
      try {
        res = await fetch(`${BASE_URL}/api/v1/auth/password-reset/request/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
      } catch {
        setGeneralError("Não foi possível conectar ao servidor. Tente novamente.");
        return;
      }

      if (res.status === 429) {
        const retryHeader = res.headers.get("Retry-After");
        const seconds = retryHeader ? parseInt(retryHeader, 10) : 60;
        setRetryAfter(isNaN(seconds) ? 60 : seconds);
        return;
      }

      setSubmitted(true);
    });
  }

  const isBlocked = pending || retryAfter > 0;

  return (
    <>
      <h1 className="text-2xl font-semibold text-foreground mb-1">
        Recuperar senha
      </h1>
      <p className="text-sm text-text-muted mb-6">
        Informe o e-mail da sua conta e enviaremos um link para redefinir sua senha.
      </p>

        {submitted ? (
          <div
            role="status"
            aria-live="polite"
            className="rounded-md border border-border bg-surface-muted px-3 py-3"
          >
            <p className="text-sm text-foreground">{MENSAGEM_GENERICA}</p>
            <div className="mt-4">
              <Link
                href="/login"
                className="text-sm font-medium text-primary hover:underline"
              >
                Voltar para o login
              </Link>
            </div>
          </div>
        ) : (
          <>
            {(generalError || retryAfter > 0) && (
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
                    : generalError}
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
                  aria-invalid={!!emailError}
                  aria-describedby={emailError ? "error-email" : undefined}
                  className={`${inputBase} ${emailError ? inputErrorCls : ""}`}
                />
                {emailError && (
                  <p id="error-email" className="text-xs text-error mt-0.5">{emailError}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isBlocked}
                className="mt-1 h-10 rounded-md bg-primary text-white text-sm font-medium flex items-center justify-center gap-2 transition-colors hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {pending ? (
                  <>
                    <Spinner />
                    <span>Enviando...</span>
                  </>
                ) : (
                  "Enviar link de redefinição"
                )}
              </button>

              <div className="text-center">
                <Link
                  href="/login"
                  className="text-sm text-text-muted hover:text-primary transition-colors"
                >
                  Voltar para o login
                </Link>
              </div>
            </form>
          </>
        )}
    </>
  );
}
