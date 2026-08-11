"use client";

import { useEffect, useState } from "react";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { getAtividade, type AtividadeDetail } from "@/app/lib/atividades";
import { AtividadeForm } from "../../_components/AtividadeForm";

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

function HeaderSlot() {
  return (
    <PageHeader>
      <span className="truncate text-base font-semibold text-text">
        Atividades
      </span>
    </PageHeader>
  );
}

export default function EditarAtividadePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<Status>("loading");
  const [atividade, setAtividade] = useState<AtividadeDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }
    const controller = new AbortController();
    setStatus("loading");

    getAtividade(id, controller.signal)
      .then((data) => {
        setAtividade(data);
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
        <div
          role="status"
          className="mx-auto flex min-h-[40vh] max-w-4xl items-center justify-center gap-2 text-sm text-text-muted"
        >
          <Spinner className="h-5 w-5 animate-spin" />
          Carregando atividades…
        </div>
      </>
    );
  }

  if (status === "error" || !atividade) {
    return (
      <>
        <HeaderSlot />
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">
            Não foi possível carregar a atividade para edição. Tente novamente.
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
            { label: "Atividades", href: "/sgp/atividades" },
            { label: atividade.titulo },
            { label: "Editar" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Editar atividade
          </h1>
          <p className="mt-1 text-sm text-text-muted">{atividade.titulo}</p>
        </div>

        <AtividadeForm
          mode="edit"
          atividadeId={id}
          initialData={atividade}
        />
      </div>
    </>
  );
}
