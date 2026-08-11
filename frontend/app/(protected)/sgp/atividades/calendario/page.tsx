"use client";

import { Suspense } from "react";
import Spinner from "@/app/components/icons/Spinner";
import { CalendarioView } from "./_components/CalendarioView";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

/**
 * Tela de calendário de atividades (Dia/Semana/Mês) — Issue #132.
 * Consome BE-3 (Issue #126) e navega para /sgp/atividades/nova/ com pré-preenchimento.
 */
export default function CalendarioPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <CalendarioView />
    </Suspense>
  );
}
