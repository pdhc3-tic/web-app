"use client";

import Link from "next/link";
import type { Route } from "next";
import { ChevronRight, ListTree, SlidersHorizontal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import Spinner from "@/app/components/icons/Spinner";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";

type Configuracao = { href: Route; titulo: string; descricao: string; Icon: LucideIcon };

/**
 * Configurações do sistema, por módulo (#319). Só Super Admin, o mesmo gate
 * das telas filhas. Nova configuração = novo item na seção do módulo.
 */
const SECOES: { modulo: string; itens: Configuracao[] }[] = [
  {
    modulo: "SGD",
    itens: [
      {
        href: "/admin/configuracoes/sgd/tipos-rubricas" as Route,
        titulo: "Tipos e Rubricas",
        descricao:
          "De qual rubrica do orçamento sai o recurso de cada tipo de solicitação (diárias, passagens, veículos…).",
        Icon: ListTree,
      },
      {
        href: "/admin/configuracoes/sgd/integracao-arlo" as Route,
        titulo: "Integração Arlo",
        descricao: "Quais campos do SGD saem no CSV enviado ao Arlo, em que ordem, e como o retorno é lido.",
        Icon: SlidersHorizontal,
      },
    ],
  },
];

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Configurações</h1>
    </PageHeader>
  );
}

export default function ConfiguracoesPage() {
  const { loading, isSuperAdmin } = useIsSuperAdmin();

  if (loading) {
    return (
      <>
        <HeaderSlot />
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
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
        <Breadcrumb items={[{ label: "Início", href: "/dashboard" }, { label: "Configurações" }]} />

        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Configurações</h2>
          <p className="mt-1 text-sm text-text-muted">Parâmetros dos módulos do sistema.</p>
        </div>

        {SECOES.map(({ modulo, itens }) => (
          <section key={modulo} className="flex flex-col gap-3" aria-label={modulo}>
            <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">{modulo}</h3>
            <ul className="flex flex-col gap-3">
              {itens.map(({ href, titulo, descricao, Icon }) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="group flex items-start gap-4 rounded-lg border border-border bg-surface p-5 transition hover:border-primary hover:bg-surface-muted/40 focus-visible:border-primary focus-visible:outline-none"
                    data-testid={`configuracao-card-${href.split("/").pop()}`}
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
          </section>
        ))}
      </div>
    </>
  );
}
