"use client";

import { useSession } from "next-auth/react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import {
  DashboardCardIcon,
  type DashboardCardIconName,
} from "@/app/components/icons";

const PLACEHOLDER_CARDS: { label: string; icon: DashboardCardIconName }[] = [
  { label: "Famílias atendidas", icon: "users" },
  { label: "Atividades", icon: "calendar" },
  { label: "Eventos", icon: "megaphone" },
  { label: "Demandas", icon: "clipboard" },
];

function getPrimeiroNome(nome: string): string {
  return nome.split(" ").filter(Boolean)[0] ?? "";
}

function getSaudacao(date: Date = new Date()): string {
  const h = date.getHours();
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

export default function DashboardPage() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  const { nome_completo } = session!.user;
  const nome = nome_completo || "Usuário";
  const primeiroNome = getPrimeiroNome(nome) || "por aqui";
  const saudacao = getSaudacao();

  return (
    <>
      <PageHeader>
        <h1 className="text-base font-semibold text-text truncate">Dashboard</h1>
      </PageHeader>

      <div className="max-w-6xl mx-auto space-y-6">
        <section className="relative overflow-hidden rounded-lg border border-border bg-primary text-surface p-6 sm:p-8">
          <div
            aria-hidden="true"
            className="absolute -top-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl"
          />
          <div className="relative">
            <p className="text-xs uppercase tracking-[0.2em] text-white/70 font-medium">
              Painel inicial
            </p>
            <h2 className="mt-3 text-2xl sm:text-3xl font-semibold leading-tight">
              {saudacao}, {primeiroNome}.
            </h2>
            <p className="mt-3 text-sm text-white/80 max-w-md leading-relaxed">
              Os indicadores dos módulos vão aparecer aqui conforme as funcionalidades forem liberadas.
            </p>
          </div>
        </section>

        <section
          aria-label="Indicadores"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {PLACEHOLDER_CARDS.map((card) => (
            <div
              key={card.label}
              className="group rounded-lg border border-border bg-surface p-5 transition-colors hover:border-primary/40"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  {card.label}
                </p>
                <span className="text-primary opacity-60 group-hover:opacity-100 transition-opacity">
                  <DashboardCardIcon name={card.icon} />
                </span>
              </div>
              <p className="mt-3 text-3xl font-semibold text-text tabular-nums">
                —
              </p>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
