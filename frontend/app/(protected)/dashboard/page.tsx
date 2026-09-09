"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { fetchAtividadeCount } from "@/app/lib/atividades";
import { fetchPainel } from "@/app/lib/painel";
import { canManageWorkPlan } from "@/app/lib/auth/roles";

type CardState =
  | { phase: "loading" }
  | { phase: "ok"; count: number }
  | { phase: "error" };

function getPrimeiroNome(nome: string): string {
  return nome.split(" ").filter(Boolean)[0] ?? "";
}

function getSaudacao(date: Date = new Date()): string {
  const h = date.getHours();
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

function AlertCard({
  title,
  description,
  state,
  href,
}: {
  title: string;
  description: string;
  state: CardState;
  href: string;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
          {title}
        </p>
        <p className="mt-1 text-xs text-text-muted">{description}</p>
      </div>

      {state.phase === "loading" && (
        <div className="h-8 w-16 animate-pulse rounded bg-surface-muted" />
      )}

      {state.phase === "error" && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Não foi possível carregar
        </div>
      )}

      {state.phase === "ok" && state.count === 0 && (
        <div className="flex items-center gap-2 text-sm text-success-text">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          Nenhuma pendência
        </div>
      )}

      {state.phase === "ok" && state.count > 0 && (
        <div className="flex items-end justify-between gap-2">
          <span className="text-3xl font-semibold tabular-nums text-error-text">
            {state.count}
          </span>
          <Link
            href={href}
            className="text-xs font-medium text-primary underline-offset-2 hover:underline"
          >
            Ver listagem →
          </Link>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { data: session, status } = useSession();

  const [semEvidencia, setSemEvidencia] = useState<CardState>({ phase: "loading" });
  const [atrasadas, setAtrasadas] = useState<CardState>({ phase: "loading" });
  const [acoesCriticas, setAcoesCriticas] = useState<CardState>({ phase: "loading" });

  useEffect(() => {
    if (status !== "authenticated" || !session) return;

    const isGlobal = canManageWorkPlan(session.user);
    const territorioId = isGlobal
      ? undefined
      : session.user.territorios[0]?.id
        ? String(session.user.territorios[0].id)
        : undefined;

    const controller = new AbortController();

    fetchAtividadeCount(
      { status: "concluido_sem_evidencia", territorioId },
      controller.signal,
    )
      .then((c) => setSemEvidencia({ phase: "ok", count: c }))
      .catch(() => setSemEvidencia({ phase: "error" }));

    fetchAtividadeCount(
      { atrasada: true, territorioId },
      controller.signal,
    )
      .then((c) => setAtrasadas({ phase: "ok", count: c }))
      .catch(() => setAtrasadas({ phase: "error" }));

    fetchPainel(
      territorioId ? { territorio_id: territorioId } : {},
      controller.signal,
    )
      .then((data) => {
        const total = data.metas.reduce((sum, m) => sum + m.resumo.vermelho, 0);
        setAcoesCriticas({ phase: "ok", count: total });
      })
      .catch(() => setAcoesCriticas({ phase: "error" }));

    return () => controller.abort();
  }, [session, status]);

  if (status === "loading") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const nome = session!.user.nome_completo || "Usuário";
  const primeiroNome = getPrimeiroNome(nome) || "por aqui";

  const territorioId = canManageWorkPlan(session!.user)
    ? undefined
    : session!.user.territorios[0]?.id;
  const territorioParam = territorioId ? `&territorio=${territorioId}` : "";
  const painelParam = territorioId ? `?territorio_id=${territorioId}` : "";

  return (
    <>
      <PageHeader>
        <h1 className="truncate text-base font-semibold text-text">Dashboard</h1>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6">
        <section className="relative overflow-hidden rounded-lg border border-border bg-primary p-6 text-surface sm:p-8">
          <div
            aria-hidden="true"
            className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/10 blur-3xl"
          />
          <div className="relative">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-white/70">
              Painel inicial
            </p>
            <h2 className="mt-3 text-2xl font-semibold leading-tight sm:text-3xl">
              {getSaudacao()}, {primeiroNome}.
            </h2>
          </div>
        </section>

        <section aria-label="Alertas do SGP" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <AlertCard
            title="Sem evidência"
            description="Atividades concluídas sem registro de evidência"
            state={semEvidencia}
            href={`/sgp/atividades?status=concluido_sem_evidencia${territorioParam}`}
          />
          <AlertCard
            title="Atrasadas"
            description="Atividades com data de fim ultrapassada ainda abertas"
            state={atrasadas}
            href={`/sgp/atividades?atrasada=true${territorioParam}`}
          />
          <AlertCard
            title="Ações críticas"
            description="Ações do Plano de Trabalho com execução abaixo do esperado"
            state={acoesCriticas}
            href={`/sgp/painel${painelParam}`}
          />
        </section>
      </div>
    </>
  );
}
