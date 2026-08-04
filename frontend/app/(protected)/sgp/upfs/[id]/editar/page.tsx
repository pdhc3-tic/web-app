"use client";

import { useEffect, useState } from "react";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { getUpfDetail, type UpfDetail } from "@/app/lib/upfs";
import { UpfWizard } from "@/app/(protected)/sgp/upfs/_components/UpfWizard";
import { UpfDetailSkeleton } from "@/app/(protected)/sgp/upfs/[id]/_components/UpfDetailSkeleton";

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

function HeaderSlot() {
  return (
    <PageHeader>
      <span className="truncate text-base font-semibold text-text">UPFs</span>
    </PageHeader>
  );
}

export default function EditarUpfPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<Status>("loading");
  const [upf, setUpf] = useState<UpfDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }
    const controller = new AbortController();
    setStatus("loading");

    getUpfDetail(id, controller.signal)
      .then((data) => {
        setUpf(data);
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
        <UpfDetailSkeleton />
      </>
    );
  }

  if (status === "error" || !upf) {
    return (
      <>
        <HeaderSlot />
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">
            Não foi possível carregar a UPF para edição. Tente novamente.
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
            { label: "UPFs", href: "/sgp/upfs" },
            { label: upf.titular.nome_completo, href: `/sgp/upfs/${id}` },
            { label: "Editar" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Editar UPF
          </h1>
          <p className="mt-1 text-sm text-text-muted">{upf.titular.nome_completo}</p>
        </div>

        <UpfWizard mode="edit" upfId={id} initialData={upf} />
      </div>
    </>
  );
}
