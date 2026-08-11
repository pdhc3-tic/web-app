"use client";

import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import Spinner from "@/app/components/icons/Spinner";
import { AtividadeForm } from "../_components/AtividadeForm";
import type { AtividadeFormData } from "../_components/formModel";

/**
 * Aceita pré-preenchimento por querystring — usado principalmente pela tela de
 * calendário (Issue #132) ao clicar em um dia vazio.
 * Parâmetros: `data_inicio`, `data_fim`, `tecnico_responsavel` (id).
 */
function useInitialPatchFromQuery(): Partial<AtividadeFormData> | undefined {
  const params = useSearchParams();
  return useMemo(() => {
    const patch: Partial<AtividadeFormData> = {};
    const di = params.get("data_inicio");
    const df = params.get("data_fim");
    const tecnico = params.get("tecnico_responsavel");
    if (di) patch.data_inicio = di;
    if (df) patch.data_fim = df;
    if (tecnico) patch.tecnico_responsavel = tecnico;
    return Object.keys(patch).length > 0 ? patch : undefined;
  }, [params]);
}

function NovaAtividadeView() {
  const initialFormPatch = useInitialPatchFromQuery();

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

        <AtividadeForm mode="create" initialFormPatch={initialFormPatch} />
      </div>
    </>
  );
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

export default function NovaAtividadePage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <NovaAtividadeView />
    </Suspense>
  );
}
