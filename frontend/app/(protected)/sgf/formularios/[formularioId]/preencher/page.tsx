"use client";

import { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, Construction } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import Spinner from "@/app/components/icons/Spinner";

/**
 * Placeholder do motor de preenchimento do SGF (#181).
 *
 * O motor real será entregue em issue futura pelo time do SGF. Este stub:
 * - Reserva a rota `/sgf/formularios/{formularioId}/preencher?upf={upfId}`
 *   (namespace `/sgf/` isolado do SGP).
 * - Exibe os parâmetros recebidos como confirmação de contrato.
 * - Oferece um link de volta pra ficha da UPF de origem quando o contexto veio
 *   preenchido.
 *
 * Contrato de entrada:
 * - path param `formularioId` — id do FormularioSGF a preencher.
 * - query param `upf` — id numérico da UPF (contexto obrigatório para o
 *   preenchimento). Sem `upf`, o placeholder informa que o contexto é
 *   obrigatório mas segue permitindo voltar.
 */
export default function PreencherFormularioPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <PreencherView />
    </Suspense>
  );
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function PreencherView() {
  const params = useParams<{ formularioId: string }>();
  const searchParams = useSearchParams();
  const upfId = searchParams.get("upf") ?? "";

  const voltarHref = upfId ? `/sgp/upfs/${upfId}#formularios` : "/sgp/upfs";

  return (
    <div data-testid="preencher-formulario-placeholder">
      <PageHeader>
        <h1 className="truncate text-base font-semibold text-text">
          Preencher formulário
        </h1>
      </PageHeader>

      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGF", href: "/sgp" },
            { label: "Preencher formulário" },
          ]}
        />

        <div className="rounded-lg border border-border bg-surface">
          <EmptyState
            icon={<Construction className="h-7 w-7" />}
            title="Motor de preenchimento em desenvolvimento"
            description={
              <>
                Esta rota é o ponto de entrada reservado para o motor de
                preenchimento do SGF. A tela em si será entregue em uma issue
                futura.
                <br />
                <br />
                <span className="text-text">
                  Formulário selecionado:{" "}
                  <code className="rounded bg-surface-muted px-1.5 py-0.5 text-xs">
                    {params.formularioId ?? "—"}
                  </code>
                </span>
                <br />
                <span className="text-text">
                  UPF de contexto:{" "}
                  <code className="rounded bg-surface-muted px-1.5 py-0.5 text-xs">
                    {upfId || "(não informada)"}
                  </code>
                </span>
              </>
            }
            action={
              <Button
                as="a"
                href={voltarHref}
                variant="secondary"
                leftIcon={<ArrowLeft className="h-4 w-4" />}
              >
                Voltar
              </Button>
            }
          />
        </div>
      </div>
    </div>
  );
}
