"use client";

import { useEffect, useState } from "react";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { getUfpaDetail, type UfpaDetail } from "@/app/lib/ufpas";
import { UfpaWizard } from "@/app/(protected)/sgp/ufpas/_components/UfpaWizard";
import { UfpaDetailSkeleton } from "@/app/(protected)/sgp/ufpas/[id]/_components/UfpaDetailSkeleton";

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

function HeaderSlot() {
  return (
    <PageHeader>
      <span className="truncate text-base font-semibold text-text">UFPAs</span>
    </PageHeader>
  );
}

export default function EditarUfpaPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<Status>("loading");
  const [ufpa, setUfpa] = useState<UfpaDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }
    const controller = new AbortController();
    setStatus("loading");

    getUfpaDetail(id, controller.signal)
      .then((data) => {
        setUfpa(data);
        setStatus("ok");
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) setStatus("notfound");
        else if (e instanceof ApiError && e.status === 403)
          setStatus("forbidden");
        else setStatus("error");
      });

    return () => controller.abort();
  }, [id, reloadKey]);

  if (status === "notfound") {
    notFound();
  }

  if (status === "forbidden") {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  if (status === "loading") {
    return (
      <>
        <HeaderSlot />
        <UfpaDetailSkeleton />
      </>
    );
  }

  if (status === "error" || !ufpa) {
    return (
      <>
        <HeaderSlot />
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">
            Não foi possível carregar a UFPA para edição. Tente novamente.
          </p>
          <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)}>
            Tentar novamente
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <HeaderSlot />

      <div className="mx-auto max-w-4xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UFPAs", href: "/sgp/ufpas" },
            { label: ufpa.titular.nome_completo, href: `/sgp/ufpas/${id}` },
            { label: "Editar" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Editar UFPA
          </h1>
          <p className="mt-1 text-sm text-text-muted">{ufpa.titular.nome_completo}</p>
        </div>

        <UfpaWizard mode="edit" ufpaId={id} initialData={ufpa} />
      </div>
    </>
  );
}
