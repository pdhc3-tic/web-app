"use client";

import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { UfpaWizard } from "@/app/(protected)/sgp/ufpas/_components/UfpaWizard";

export default function NovaUfpaPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">
          Nova UFPA
        </span>
      </PageHeader>

      <div className="mx-auto max-w-4xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UFPAs", href: "/sgp/ufpas" },
            { label: "Nova" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Nova UFPA
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Preencha os quatro passos para cadastrar a Unidade Familiar de Produção Agropecuária.
          </p>
        </div>

        <UfpaWizard mode="create" />
      </div>
    </>
  );
}
