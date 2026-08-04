"use client";

import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { AtividadeForm } from "../_components/AtividadeForm";

export default function NovaAtividadePage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">
          Nova atividade
        </span>
      </PageHeader>

      <div className="mx-auto max-w-4xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Atividades", href: "/sgp/atividades" },
            { label: "Nova" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Nova atividade
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Registre a atividade de campo e vincule-a a uma Ação do Plano de
            Trabalho.
          </p>
        </div>

        <AtividadeForm mode="create" />
      </div>
    </>
  );
}
