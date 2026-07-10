"use client";

import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { UpfWizard } from "@/app/(protected)/sgp/upfs/_components/UpfWizard";

export default function NovaUpfPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">
          Nova UPF
        </span>
      </PageHeader>

      <div className="mx-auto max-w-4xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UPFs", href: "/sgp/upfs" },
            { label: "Nova" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Nova UPF
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Preencha os quatro passos para cadastrar a unidade produtiva familiar.
          </p>
        </div>

        <UpfWizard mode="create" />
      </div>
    </>
  );
}
