"use client";

import { Suspense, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Spinner from "@/app/components/ui/Spinner";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function validatePassword(senha: string): string | null {
  if (senha.length < 10) return "A senha deve ter no mínimo 10 caracteres.";
  if (!/[A-Z]/.test(senha)) return "A senha deve conter pelo menos 1 letra maiúscula.";
  if (!/[0-9]/.test(senha)) return "A senha deve conter pelo menos 1 número.";
  return null;
}

const inputBase =
  "h-10 w-full rounded-md border px-3 text-sm text-text bg-surface outline-none transition" +
  " focus:ring-2 focus:ring-primary/15 focus:border-primary" +
  " border-border placeholder:text-text-muted";
const inputErrorCls = "border-error focus:ring-error/20 focus:border-error";

type FieldErrors = { senha?: string; confirm?: string };

function RedefinirSenhaForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [pending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [tokenInvalido, setTokenInvalido] = useState(false);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const form = e.currentTarget;
    const senha = (form.elements.namedItem("senha") as HTMLInputElement).value;
    const confirm = (form.elements.namedItem("confirm") as HTMLInputElement).value;

    const errs: FieldErrors = {};
    const senhaErr = validatePassword(senha);
    if (senhaErr) errs.senha = senhaErr;
    if (confirm !== senha) errs.confirm = "As senhas não coincidem.";

    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setGlobalError(null);
      setTokenInvalido(false);
      return;
    }
    setFieldErrors({});
    setGlobalError(null);
    setTokenInvalido(false);

    if (!token) {
      setGlobalError("Token de redefinição ausente. Solicite um novo link.");
      setTokenInvalido(true);
      return;
    }

    startTransition(async () => {
      let res: Response;
      try {
        res = await fetch(`${BASE_URL}/api/v1/auth/password-reset/confirm/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, nova_senha: senha }),
        });
      } catch {
        setGlobalError("Não foi possível conectar ao servidor. Tente novamente.");
        return;
      }

      if (res.ok) {
        router.push("/login?reset=ok");
        return;
      }

      if (res.status === 400) {
        try {
          const body: { code?: string; message?: string } = await res.json();
          if (body.code === "INVALID_TOKEN" || body.code === "EXPIRED_TOKEN") {
            setGlobalError(body.message ?? "Link inválido ou expirado.");
            setTokenInvalido(true);
            return;
          }
          setGlobalError(body.message ?? "Não foi possível redefinir a senha.");
        } catch {
          setGlobalError("Não foi possível redefinir a senha.");
        }
        return;
      }

      setGlobalError("Erro inesperado. Tente novamente.");
    });
  }

  return (
    <>
      <h1 className="text-2xl font-semibold text-text mb-1">
        Redefinir senha
      </h1>
      <p className="text-sm text-text-muted mb-6">
        Escolha uma nova senha com no mínimo 10 caracteres, 1 letra maiúscula e 1 número.
      </p>

        {globalError && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-5 rounded-md border border-error bg-error-bg px-3 py-2.5"
          >
            <div className="flex items-start gap-2">
              <svg className="mt-0.5 h-4 w-4 shrink-0 text-error" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <p className="text-sm text-error">{globalError}</p>
            </div>
            {tokenInvalido && (
              <div className="mt-2 pl-6">
                <Link
                  href="/esqueci-minha-senha"
                  className="text-sm font-medium text-error hover:underline"
                >
                  Solicitar novo link
                </Link>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="senha" className="text-sm font-medium text-text">
              Nova senha
            </label>
            <input
              id="senha"
              name="senha"
              type="password"
              autoComplete="new-password"
              required
              aria-invalid={!!fieldErrors.senha}
              aria-describedby={fieldErrors.senha ? "error-senha" : undefined}
              className={`${inputBase} ${fieldErrors.senha ? inputErrorCls : ""}`}
            />
            {fieldErrors.senha && (
              <p id="error-senha" className="text-xs text-error mt-0.5">{fieldErrors.senha}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="confirm" className="text-sm font-medium text-text">
              Confirmar nova senha
            </label>
            <input
              id="confirm"
              name="confirm"
              type="password"
              autoComplete="new-password"
              required
              aria-invalid={!!fieldErrors.confirm}
              aria-describedby={fieldErrors.confirm ? "error-confirm" : undefined}
              className={`${inputBase} ${fieldErrors.confirm ? inputErrorCls : ""}`}
            />
            {fieldErrors.confirm && (
              <p id="error-confirm" className="text-xs text-error mt-0.5">{fieldErrors.confirm}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={pending}
            className="mt-1 h-10 rounded-md bg-primary text-white text-sm font-medium flex items-center justify-center gap-2 transition-colors hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pending ? (
              <>
                <Spinner />
                <span>Redefinindo...</span>
              </>
            ) : (
              "Redefinir senha"
            )}
          </button>
        </form>
    </>
  );
}

export default function RedefinirSenhaPage() {
  return (
    <Suspense>
      <RedefinirSenhaForm />
    </Suspense>
  );
}
