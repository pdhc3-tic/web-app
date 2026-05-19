"use client";

import { useSession } from "next-auth/react";
import { LogoutButton } from "./logout-button";

type CardIcon = "users" | "calendar" | "megaphone" | "clipboard";

const PLACEHOLDER_CARDS: { label: string; icon: CardIcon }[] = [
  { label: "Famílias atendidas", icon: "users" },
  { label: "Atividades", icon: "calendar" },
  { label: "Eventos", icon: "megaphone" },
  { label: "Demandas", icon: "clipboard" },
];

function getIniciais(nome: string): string {
  const partes = nome.split(" ").filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0][0]?.toUpperCase() ?? "?";
  return (
    (partes[0][0] ?? "") + (partes[partes.length - 1][0] ?? "")
  ).toUpperCase();
}

function getPrimeiroNome(nome: string): string {
  return nome.split(" ").filter(Boolean)[0] ?? "";
}

function getSaudacao(date: Date = new Date()): string {
  const h = date.getHours();
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

function CardIconSvg({ name }: { name: CardIcon }) {
  const props = {
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: "currentColor",
    strokeWidth: 1.5,
    className: "h-5 w-5",
    "aria-hidden": true,
  };
  switch (name) {
    case "users":
      return (
        <svg {...props}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
          />
        </svg>
      );
    case "calendar":
      return (
        <svg {...props}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
          />
        </svg>
      );
    case "megaphone":
      return (
        <svg {...props}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 1 1 0-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 0 1-1.44-4.282m3.102.069a18.03 18.03 0 0 1-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 0 1 8.835 2.535M10.34 6.66a23.847 23.847 0 0 0 8.835-2.535m0 0A23.74 23.74 0 0 0 18.795 3m.38 1.125a23.91 23.91 0 0 1 1.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 0 0 1.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 0 1 0 3.46"
          />
        </svg>
      );
    case "clipboard":
      return (
        <svg {...props}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2Z"
          />
        </svg>
      );
  }
}

function BrandMark() {
  return (
    <div className="flex items-center gap-2 text-primary">
      <svg
        viewBox="0 0 24 24"
        className="h-6 w-6"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 3 L20 19 L4 19 Z"
        />
      </svg>
      <span className="text-base font-semibold tracking-tight">
        PDHC <span className="font-light italic lowercase opacity-80">iii</span>
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  const { nome_completo, foto_url, perfis } = session!.user;
  const nome = nome_completo || "Usuário";
  const primeiroNome = getPrimeiroNome(nome) || "por aqui";
  const iniciais = getIniciais(nome);
  const saudacao = getSaudacao();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-surface">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <BrandMark />
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex items-center gap-3 min-w-0">
              {foto_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={foto_url}
                  alt=""
                  className="h-9 w-9 rounded-full object-cover border border-border shrink-0"
                />
              ) : (
                <div
                  aria-hidden="true"
                  className="h-9 w-9 rounded-full bg-primary text-white text-xs font-medium flex items-center justify-center shrink-0"
                >
                  {iniciais}
                </div>
              )}
              <div className="min-w-0 hidden sm:block">
                <p className="text-sm font-medium text-foreground truncate leading-tight">
                  {nome}
                </p>
                {perfis && perfis.length > 0 ? (
                  <ul className="mt-1 flex flex-wrap gap-1">
                    {perfis.map((perfil) => (
                      <li
                        key={perfil.slug}
                        className="px-1.5 py-0.5 rounded-full bg-surface-muted text-[10px] font-medium uppercase tracking-wide text-text-muted border border-border"
                      >
                        {perfil.nome}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
            <LogoutButton />
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <section className="relative overflow-hidden rounded-lg border border-border bg-primary text-white p-6 sm:p-8">
          <div
            aria-hidden="true"
            className="absolute -top-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl"
          />
          <div className="relative">
            <p className="text-sm text-white/80 uppercase tracking-wider font-medium">
              Painel · Sprint 1
            </p>
            <h1 className="mt-2 text-2xl sm:text-3xl font-semibold leading-tight">
              {saudacao}, {primeiroNome}.
            </h1>
            <p className="mt-2 text-sm text-white/80 max-w-md">
              Seu painel está em construção. As métricas dos módulos aparecerão aqui
              conforme forem entregues.
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
                  <CardIconSvg name={card.icon} />
                </span>
              </div>
              <p className="mt-3 text-3xl font-semibold text-foreground tabular-nums">
                —
              </p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
