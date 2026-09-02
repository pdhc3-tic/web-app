"use client";

import Link from "next/link";
import type { Route } from "next";
import { BarChart3, CalendarClock, ChevronRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import Spinner from "@/app/components/icons/Spinner";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";

/**
 * Hub de integrações admin. Só Super Admin, mesmo gate das telas filhas.
 * A lista aqui é o ponto único de manutenção — para adicionar nova
 * integração, basta acrescentar um item em INTEGRACOES.
 */
const INTEGRACOES: {
  href: Route;
  titulo: string;
  descricao: string;
  Icon: LucideIcon;
}[] = [
  {
    href: "/admin/integracoes/google-calendar" as Route,
    titulo: "Google Calendar",
    descricao:
      "Calendário destino e lembretes das atividades sincronizadas com a agenda dos técnicos.",
    Icon: CalendarClock,
  },
  {
    href: "/admin/integracoes/power-bi" as Route,
    titulo: "Power BI",
    descricao:
      "Endpoint de exportação consumido pelo Power BI, token de serviço e status do último snapshot.",
    Icon: BarChart3,
  },
];

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Integrações
      </h1>
    </PageHeader>
  );
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

export default function IntegracoesHubPage() {
  const { loading, isSuperAdmin } = useIsSuperAdmin();

  if (loading) {
    return (
      <>
        <HeaderSlot />
        <CenteredSpinner />
      </>
    );
  }

  if (!isSuperAdmin) {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  return (
    <>
      <HeaderSlot />

      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Breadcrumb
          items={[{ label: "Início", href: "/dashboard" }, { label: "Integrações" }]}
        />

        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">
            Integrações
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Configurações das integrações externas do sistema.
          </p>
        </div>

        <ul className="flex flex-col gap-3">
          {INTEGRACOES.map(({ href, titulo, descricao, Icon }) => (
            <li key={href}>
              <Link
                href={href}
                className="group flex items-start gap-4 rounded-lg border border-border bg-surface p-5 transition hover:border-primary hover:bg-surface-muted/40 focus-visible:border-primary focus-visible:outline-none"
                data-testid={`integracao-card-${href.split("/").pop()}`}
              >
                <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted transition group-hover:bg-primary/10 group-hover:text-primary">
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-text">{titulo}</p>
                  <p className="mt-1 text-sm text-text-muted">{descricao}</p>
                </div>
                <ChevronRight className="h-5 w-5 shrink-0 text-text-muted transition group-hover:text-primary" />
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
